"""Iteration 66 census repair (review-1 R1-CB-01..06, R1-CR-02/03/04/07, R1-CB-05 splits, re-search).

Replays on the iteration-65 census TSVs (the *.before.tsv copies beside this tool when present, else extracted with
`git show fb6660a0:...`) and writes the live TSVs plus ledger.tsv (every column change on a retained row) and scope.tsv (every added row: splits and the
R1-CB-06 addition). Run from the repository root:

    python3 $G5_RUN_STATE/scratch/iteration-66/census/tools/apply.py
"""
import csv, os, sys
sys.path.insert(0, '.g5/Verus_verification/tools')
import census as C

HERE = os.path.dirname(os.path.abspath(__file__))
SCR = os.path.dirname(HERE)
V = '.g5/Verus_verification'
M = f'{V}/models'
csv.field_size_limit(10 ** 9)


def latest(model, kind='proof', name=None):
    L = C.latest_receipts(f'{V}/results/{model}')
    p = L.get(('control', name) if kind == 'control' else (kind, None))
    assert p, (model, kind, name)
    return p


def prove(m): return latest(m)
def bind(m): return latest(m, 'binding')
def ctl(m, n): return latest(m, 'control', n)
def loc(m, item, f=None): return f'{M}/{m}/{f or m}.rs::{item}'


BASE = 'fb6660a0'  # review-1 commit = the iteration-65 census


def before(name, cols):
    p = f'{SCR}/{name}.before.tsv'
    if not os.path.exists(p):  # replay from the repository: extract the TSV at the base commit
        import subprocess, tempfile
        p = os.path.join(tempfile.mkdtemp(), f'{name}.tsv')
        with open(p, 'wb') as f:
            f.write(subprocess.check_output(['git', 'show', f'{BASE}:.g5/Verus_verification/census/{name}.tsv']))
    return C.read_tsv(p, cols)


orows = before('obligations', C.OBL_COLS)
brows = before('blocks', C.BLOCKS_COLS)
erows = before('excluded', C.EXC_COLS)
byid = {r['id']: r for r in orows}
ledger, scope = [], []
IT = '66'


def setc(oid, reason, **cols):
    r = byid[oid]
    for c, v in cols.items():
        assert c in C.OBL_COLS, c
        if r[c] != v:
            ledger.append((oid, c, r[c], v, reason))
            r[c] = v
    r['iteration'] = IT


def gs(oid, note):  # append to grade_source
    return (byid[oid]['grade_source'] + '; ' if byid[oid]['grade_source'] else '') + note


def next_id(block):
    n = max(int(r['id'].split('#o')[1]) for r in orows if r['block'] == block)
    return f'{block}#o{n + 1:02d}'


def add(base_id, reason, **cols):
    """Add a row split from base_id (or a new row when base_id names only a block)."""
    if '#' in base_id:
        base = dict(byid[base_id])
        block = base['block']
    else:
        block = base_id
        base = {c: '' for c in C.OBL_COLS}
        base['block'] = block
    r = dict(base)
    r['id'] = next_id(block)
    r['iteration'] = IT
    r.update(cols)
    # insert after the last row of the block, keeping file order
    idx = max(i for i, x in enumerate(orows) if x['block'] == block)
    orows.insert(idx + 1, r)
    byid[r['id']] = r
    scope.append((r['id'], base_id, r['grade'], r['statement'], reason))
    return r['id']


SPLIT = 'it66 split (R1-CB-05, census/README "Splitting rule")'
NOGAP = ''

# ----------------------------------------------------------------------------------------------------------------
# 1. Listed regrades
# R1-CB-01
setc('search.knn.threshold#o03', 'R1-CB-01: the theorem is a point check on sorted scores; a limit-then-filter variant '
     'satisfies every conclusion', grade='partial',
     gap='theorem_filter_precedes_limit checks one sorted 3-element input; a limit-then-filter variant of search satisfies '
         'every ensures (review-1 R1-CB-01), so the order of filter and limit is not distinguished; the census case '
         '(best row below the threshold, second above) is never exercised',
     grade_source=gs('search.knn.threshold#o03', 'it66 review-1 R1-CB-01: full -> partial (point check; limit-then-filter mutant passes)'))
# R1-CB-02
r = byid['search.fusion.python#o03']
setc('search.fusion.python#o03', 'R1-CB-02: the fused sort is a premise (not modelled)', check_scope='narrowed',
     premises=r['premises'] + '; the fused sort by score is a premise (fusion_ranking NOTES: the observed consumer sorts; '
              'the theorem is per single-list rank)',
     grade_source=gs('search.fusion.python#o03', 'it66 review-1 R1-CB-02 (adjudicated): held full; check_scope full -> narrowed'))
# R1-CB-03
setc('algorithms.op.paths.weighted#o18', 'R1-CB-03: the omitted case is decided in the Python carrier, not the model',
     grade='partial',
     gap="the 'omitted' case is decided in the Python carrier (engine.py:1265-1270, None -> '[]'), outside the model, "
         "which has only the native predicate Set; weighted_fraction NOTES: no formal raw-to-Config carrier theorem",
     grade_source=gs('algorithms.op.paths.weighted#o18', 'it66 review-1 R1-CB-03: full -> partial'))
setc('graph.names#o04', 'R1-CB-03 / LINT-4: locator added (the refusal decision the model represents)',
     model_locators=loc('graph_structure', 'theorem_refusals') + '; ' + loc('erasure_stores', 'theorem_refusal_changes_nothing'),
     grade_source=gs('graph.names#o04', 'it66 LINT-4: locators added (graph_structure refusal function; erasure_stores refuse-before-write for the erase family only); grade held partial'))
setc('install.inference#o03', 'R1-CB-03 / LINT-4: locator added', model_locators=loc('inference_rows', 'theorem_retract_keeps_asserted'),
     gap='the retracted row set is modelled (theorem_retract_keeps_asserted); its ^KG adjacency effect is not in the model; the binding checks ^KG entries',
     grade_source=gs('install.inference#o03', 'it66 LINT-4: locator added; held partial (stops before the ^KG reader)'))
setc('search.plaid#o06', 'R1-CB-03 / LINT-4: locator added', model_locators=loc('plaid_index', 'theorem_insert_accepts_other_width'),
     gap='the model admits a document of another width (theorem_insert_accepts_other_width); its score is the uninterpreted maxsim, so scoring on the common parts and the outranking are observed in the binding only',
     grade_source=gs('search.plaid#o06', 'it66 LINT-4: locator added; held partial'))
setc('search.vecindex#o10', 'R1-CB-03 / LINT-4: locator added', model_locators=loc('vec_index', 'theorem_insert_overwrites_dim'),
     gap='the model admits a vector of another width and overwrites dim (theorem_insert_overwrites_dim); the distance over the common prefix is observed in the binding (one 2-wide insert), not represented',
     grade_source=gs('search.vecindex#o10', 'it66 LINT-4: locator added; held partial'))
setc('structure.rebuild#o06', 'R1-CB-03 / LINT-4: no model item represents rows or edge reads across rebuild_edge_indices',
     grade='absent', gap='sql_procs models the rebuild answer only (theorem_rebuild_answers_four_or_raises); rows and edge reads are not in the model; observed by the binding only',
     grade_source=gs('structure.rebuild#o06', 'it66 LINT-4: partial -> absent (no model locator; partial needs one)'))
# search.fusion.python#o06 -> absent and split (R1-CB-03 + R1-CB-05)
setc('search.fusion.python#o06', 'R1-CB-03: no k or detail rule in fusion_ranking; R1-CB-05 split', grade='absent',
     statement='multi_modal_search returns at most k entities',
     locator="bullet 1: 'returns at most k entities'", cases='k=2 over 5 candidates -> 2 rows',
     gap='top-k not in fusion_ranking (observed in the 90 wrapper journeys only)',
     grade_source=gs('search.fusion.python#o06', 'it66 review-1 R1-CB-03: partial -> absent (no locator); R1-CB-05 split: detail rows -> new row'))
add('search.fusion.python#o06', SPLIT, locator="bullet 1: 'with their fused rank and each retained leg's first score and position'",
    statement="each returned entity carries its fused rank and each retained leg's first score and position",
    cases='entity in both legs -> two leg details; in one leg -> one', grade='absent', model_locators='',
    gap='detail assembly not in fusion_ranking (observed in the wrapper journeys only)',
    grade_source='new (it66 split of search.fusion.python#o06)')
# R1-CB-04
setc('structure.write#o05', 'R1-CB-04: erasure_stores (iteration 65) represents both transaction outcomes', grade='partial',
     model_locators=loc('erasure_stores', 'witness_dedicated_erase_survives_caller_rollback') + '; ' + loc('erasure_stores', 'theorem_joined_caller_decides'),
     design_check='proved', check_scope='narrowed', design_receipts=prove('erasure_stores'),
     as_built=byid['structure.write#o05']['as_built'] + '; binding AGREES ' + bind('erasure_stores'),
     premises='erasure_stores transaction model: a joined call leaves the outcome to the caller; a from_connect call commits on its own connection',
     gap="the joined outcome is the model's definition (theorem_joined_caller_decides is true by definition, review-1 R1-ER-02); the from_connect half is a point witness; observed live (E1, E6)",
     grade_source=gs('structure.write#o05', 'it66 review-1 R1-CB-04: absent -> partial (stale grade; erasure_stores iteration 65)'))
# R1-CB-06
add('ledger.commit.expected-head', 'R1-CB-06: missed obligation (the lead\'s "may name the head it expects")',
    locator="lead: 'A commit may name the head it expects'",
    statement='A commit naming the current head as its expected head commits (the next revision on that head)',
    cases='expected = current head: committed vs expected = an older revision: StaleHeadError',
    observation='commit result and the ledger head',
    model_locators=loc('ledger_client', 'theorem_expected_head_outcomes') + '; ' + loc('ledger_client', 'client_commit'),
    premises='key None, holder and counter row free, enabled', grade='partial', design_check='proved', check_scope='narrowed',
    design_receipts=prove('ledger_client'), as_built='binding AGREES ' + bind('ledger_client'),
    parent_entailment='n/a: own text',
    gap='theorem_expected_head_outcomes concludes nothing when e == head; the commit-through is server()\'s definition only (review-1 R1-CB-06)',
    grade_source='new: it66 review-1 R1-CB-06')
# R1-CR-02: install.snapshot#o04 stays an obligation (its second clause states the current exporter's behaviour)
setc('install.snapshot#o04', 'R1-CR-02: modelled by the proofs-d1b dirty-export counterexample', grade='partial',
     model_locators='experiment/playbook-completion/proofs-d1b/src/cx_fc1801.rs::counterexample_fc1801; experiment/playbook-completion/proofs-d1b/src/snap_l2.rs::step2',
     design_check='refuted', check_scope='narrowed',
     design_receipts='.g5/Verus_verification/results/playbook-proofs-d1b/20261115T035741Z-control_fc1801_dirty_export/receipt.json; .g5/Verus_verification/results/playbook-proofs-d1b/20261115T035711Z-baseline/receipt.json',
     premises='proofs-d1b reviewed design of the as-built save (no lock, uncommitted reads, snapshot.py:864-1034); one concurrent writer that rolls back',
     gap='the concurrent-writer case is refuted (the archive holds a row the namespace never committed); the quiet-writer neighbour (the archive equals one committed state) has no theorem over the as-built exporter',
     grade_source=gs('install.snapshot#o04', 'it66 review-1 R1-CR-02: absent -> partial. Kept as an obligation, not an undecided alternative: working assumption 2\'s clause "for the current exporter declare the quiet-writer premise" states current behaviour (the exporter is consistent only when writers are quiet), which rule 7 makes assessable; the policy half ("claim a consistent snapshot only ...") is the reliance rule around it'))
# R1-CR-03
setc('install.schema.classes_follow#o01', 'R1-CR-03: platform models the deploy compiling classes for the setup\'s schema',
     grade='partial', model_locators=loc('platform', 's_step') + '; ' + loc('platform', 'SSt'),
     gap="platform's SetupDeploy inserts the setup schema into classes_for (rewritten sources, platform.rs:80-81, 245) with no theorem concluding it; the case-variant engine spelling (bug-plt-015) is not represented (platform.rs:31-32) || owner-contradicted: deploy rewrites class sources with the engine's spelling, not the recorded schema's (bug-plt-015) (handoff-63 §6.1 #28)",
     grade_source=gs('install.schema.classes_follow#o01', 'it66 review-1 R1-CR-03: absent -> partial (modelled)'))
setc('algorithms.owner#o01', 'R1-CR-03: traversal_strategy represents the Arno-absent Owner answer for the BFS',
     grade='partial', model_locators=loc('traversal_strategy', 'theorem_fixture_path'), design_check='proved', check_scope='narrowed',
     design_receipts=prove('traversal_strategy'), as_built=byid['algorithms.owner#o01']['as_built'] + '; binding AGREES ' + bind('traversal_strategy'),
     gap='only the BFS walk\'s Arno-absent answer is represented (theorem_fixture_path: the ObjectScript Owner answers); no other algorithm\'s Owner, and random_walk\'s missing Owner, are modelled || owner-contradicted: random_walk has no Owner and returns [] with a warning without Arno (_engine/algorithms.py:658-678)',
     grade_source=gs('algorithms.owner#o01', 'it66 review-1 R1-CR-03: absent -> partial'))
# R1-CR-04
r = byid['structure.adjacency.scan#o09']
setc('structure.adjacency.scan#o09', 'R1-CR-04: the plan choice rests on unstated premises', check_scope='narrowed',
     premises=r['premises'] + '; premise (not established by the product for every hop): no inline relationship properties and an id-named, non-anonymous source (translator.py:16472-16492 conditions, sql_procs.rs:133-137); USE GRAPH \'\' supplied as named=false',
     grade_source=gs('structure.adjacency.scan#o09', 'it66 review-1 R1-CR-04: held full; check_scope full -> narrowed'))
# R1-CR-07
r = byid['install.export.rdf.report#o02']
setc('install.export.rdf.report#o02', 'R1-CR-07: the +2 blank-subject case is proved by two uncited theorems',
     model_locators=r['model_locators'] + '; ' + loc('rdf_reporting', 'theorem_envelope_has_two_derived_blank_subjects') + '; ' + loc('rdf_reporting', 'theorem_raw_rows_to_final_report'),
     grade_source=gs('install.export.rdf.report#o02', 'it66 review-1 R1-CR-07: two locators added'))

# ----------------------------------------------------------------------------------------------------------------
# 2. R1-CB-05 named splits
LC = 'ledger_client'
lcp = prove(LC); lcb = 'binding AGREES ' + bind(LC)
obs3 = dict(observation='ledger stats', premises='counter row free; requires of the cited theorem (enabled, key/holder as stated)',
            design_receipts=lcp, as_built=lcb, parent_entailment='n/a: own text', design_check='proved', check_scope='narrowed')
setc('ledger.observability#o03', 'R1-CB-05: split into one row per counted outcome', **{k: v for k, v in obs3.items()},
     locator="bullet 1: 'The counters keep the commits written'",
     statement='A written commit is counted in commits_ok (with the counter row free)',
     cases='valid commit with the row free: ok +1 vs the same commit while another transaction holds the row: refused, +0',
     model_locators=loc(LC, 'theorem_held_counter_row_refuses_a_valid_commit'), grade='full', gap=NOGAP,
     grade_source=gs('ledger.observability#o03', 'it66 R1-CB-05 split: o03 keeps the written-commit counter; the other ten counted outcomes are o07-o16; partial -> full for this outcome'))
parts = [
    ("bullet 1: '(the genesis included)'", 'The genesis written by the first enable is counted in commits_ok',
     'first enable: ok +1 vs re-enable: no count', loc(LC, 'enable'), 'partial', 'none', 'n/a', '',
     'enable() adds one to ok on the genesis (definition); theorem_enable_lifecycle does not conclude the counter'),
    ("bullet 1: 'the replays'", 'A keyed replay is counted in replays_idem',
     'retry with the same key and operations: replays +1, nothing written', loc(LC, 'theorem_retry_with_new_metadata_replays'),
     'full', 'proved', 'narrowed', ctl(LC, 'replay-counted-as-commit'), ''),
    ("bullet 1: 'a stale ... expected head'", 'A stale expected head is counted in rej_stale_head',
     'known non-head expected: stale +1 vs unknown ID: unknown +1', loc(LC, 'theorem_expected_head_outcomes'),
     'full', 'proved', 'narrowed', ctl(LC, 'unknown-as-stale'), ''),
    ("bullet 1: 'or unknown expected head'", 'An unknown expected head is counted in rej_unknown_head',
     'ID that is no revision: unknown +1 vs known non-head: stale +1', loc(LC, 'theorem_expected_head_outcomes'),
     'full', 'proved', 'narrowed', ctl(LC, 'unknown-as-stale'), ''),
    ("bullet 1: 'an idempotency conflict'", 'An idempotency conflict (same key, other operations) is counted in rej_conflict',
     'same key, operations reordered: conflict +1, nothing written', loc(LC, 'theorem_reordered_operations_conflict'),
     'full', 'proved', 'narrowed', '', ''),
    ("bullet 1: '(a key whose revision was redacted included)'", 'A commit naming a key whose revision was redacted is counted in rej_conflict',
     'redacted key reused: conflict +1', loc(LC, 'bump'), 'partial', 'none', 'n/a', '',
     'bump maps IdemRedacted to the conflict counter (definition); no theorem concludes it'),
    ("bullet 1: 'a failed operation'", 'A failed operation is counted in rej_failed_op',
     'failing op: failed +1, nothing written', loc(LC, 'theorem_failed_operation_reported'), 'full', 'proved', 'narrowed', '', ''),
    ("bullet 1: 'too many operations'", 'Too many operations is counted in rej_too_large',
     'max_ops + 1 operations: size +1; max_ops: committed', loc(LC, 'theorem_size_limit_boundary'), 'full', 'proved', 'narrowed',
     ctl(LC, 'size-limit-exclusive'), ''),
    ("bullet 1: 'a disabled ledger'", 'A commit refused by a disabled ledger is counted in rej_disabled',
     'disabled: disabled +1 vs never enabled: no counter', loc(LC, 'theorem_disabled_and_never_enabled'), 'full', 'proved', 'narrowed',
     ctl(LC, 'never-counted-as-disabled'), ''),
    ("bullet 1: 'and a lock timeout'", 'A lock-timeout refusal is counted in rej_lock_timeout',
     'head held by another transaction: lock +1 (and it survives the holder\'s rollback)',
     loc(LC, 'theorem_uncounted_nested_refusal_leaves_the_counter_row') + '; ' + loc(LC, 'theorem_nested_lock_timeout_keeps_the_counter_row'),
     'full', 'proved', 'narrowed', ctl(LC, 'nested-refusal-counted'), ''),
    ("bullet 1: 'Strict-mode refusals are counted too'", 'A strict-mode refusal is counted in rej_strict_block (with the counter row free)',
     'strict guard refusal: strict_block +1; row held elsewhere: lost', loc(LC, 'theorem_uncounted_outcomes'), 'full', 'proved', 'narrowed', '', ''),
]
for (lc, st, cs, ml, g, dc, sc, extra, gap) in parts:
    add('ledger.observability#o03', SPLIT, **{**obs3, **dict(locator=lc, statement=st, cases=cs, model_locators=ml, grade=g,
        design_check=dc, check_scope=sc, design_receipts=(lcp + ('; ' + extra if extra else '')) if dc != 'none' else '',
        gap=gap, grade_source='new (it66 split of ledger.observability#o03; review-1 R1-CB-05: ledger_client.rs:519-741)')})
setc('ledger.observability#o04', 'R1-CB-05: split into its three uncounted outcomes',
     statement='A refusal before the first enable emits a hook event and moves no counter',
     locator="bullet 2: 'a refusal before the first enable'",
     cases='never enabled: event, counters +0 vs disabled: event, rej_disabled +1',
     model_locators=loc(LC, 'theorem_disabled_and_never_enabled') + '; ' + loc(LC, 'theorem_uncounted_outcomes'),
     premises='holder and counter row free',
     design_receipts=lcp + '; ' + ctl(LC, 'never-counted-as-disabled'),
     grade_source=gs('ledger.observability#o04', 'it66 R1-CB-05 split: o04 keeps never-enabled; redaction-blocked and inconsistent are o17-o18'))
add('ledger.observability#o04', SPLIT, statement='A commit refused because it writes into an unfinished redaction\'s target emits a hook event and moves no counter',
    locator="bullet 2: 'a commit refused because it writes into an unfinished redaction's target'",
    cases='redaction-blocked: event, counters +0 vs failed op: event, rej_failed +1',
    model_locators=loc(LC, 'theorem_uncounted_outcomes'), premises='Apply.blocked supplied by ledger_redaction',
    design_receipts=lcp + '; ' + ctl(LC, 'redaction-block-counted'), grade='full', gap=NOGAP,
    grade_source='new (it66 split of ledger.observability#o04)')
add('ledger.observability#o04', SPLIT, statement='An inconsistent refusal (e.g. a revision field longer than its column) emits a hook event and moves no counter',
    locator="bullet 2: 'and an inconsistent refusal'", cases='field over its column: inconsistent event, counters +0',
    model_locators=loc(LC, 'theorem_uncounted_outcomes') + '; ' + loc(LC, 'theorem_uncounted_nested_refusal_leaves_the_counter_row'),
    premises='holder free or held by this process', design_receipts=lcp, grade='full', gap=NOGAP,
    grade_source='new (it66 split of ledger.observability#o04)')

# algorithms.op.paths.weighted
setc('algorithms.op.paths.weighted#o01', 'R1-CB-05 split: no-path outcome -> new row',
     statement='The weighted search returns a minimum-cost path, even when it has more hops than another path',
     cases='a-b cost 10 vs a-c-b cost 2: a-c-b',
     grade_source=gs('algorithms.op.paths.weighted#o01', 'it66 R1-CB-05 split: no-row outcome -> new row'))
add('algorithms.op.paths.weighted#o01', SPLIT, locator="lead: 'and returns no row when no path joins the two nodes'",
    statement='The weighted search returns no row when no path joins the two nodes', cases='disconnected endpoints: no row vs connected: one row',
    model_locators=loc('weighted_paths', 'theorem_empty_queue_is_no_feasible_path') + '; ' + loc('weighted_paths', 'theorem_complete_terminating_search'),
    grade_source='new (it66 split of algorithms.op.paths.weighted#o01)')
setc('algorithms.op.paths.weighted#o03', 'R1-CB-05 split: direction refusal -> new row',
     statement='The procedure refuses a weight property other than the stored weight', cases="weightProp 'cost': error vs 'weight': answer",
     grade_source=gs('algorithms.op.paths.weighted#o03', 'it66 R1-CB-05 split: direction -> new row'))
add('algorithms.op.paths.weighted#o03', SPLIT, locator="bullet 2: 'or a direction other than out, in or both, is refused'",
    statement='The procedure refuses any direction other than out, in or both', cases="direction 'up': error vs 'out': answer",
    grade_source='new (it66 split of algorithms.op.paths.weighted#o03)')
setc('algorithms.op.paths.weighted#o04', 'R1-CB-05 split: hop cap -> new row',
     statement='For distinct endpoints a path that costs more than the cost limit is never returned', cases='path cost = cap kept vs cap+1 rejected',
     grade_source=gs('algorithms.op.paths.weighted#o04', 'it66 R1-CB-05 split: hop limit -> new row'))
add('algorithms.op.paths.weighted#o04', SPLIT, locator="bullet 3: 'or has more hops than a positive hop limit'",
    statement='For distinct endpoints a path with more hops than a positive hop limit is never returned', cases='hops = limit kept vs limit+1 rejected',
    model_locators=loc('weighted_paths', 'theorem_complete_terminating_search') + '; ' + loc('weighted_paths', 'theorem_actual_returned_path_is_optimal'),
    design_receipts=prove('weighted_paths'), grade_source='new (it66 split of algorithms.op.paths.weighted#o04)')
setc('algorithms.op.paths.weighted#o06', 'R1-CB-05 split (named): Python refusal vs native outcome',
     statement='The public procedure refuses a negative hop limit', cases='maxHops -1 through the public procedure: error',
     observation='error', gap='negative public hops are outside the formal Config domain (weighted_paths NOTES)',
     grade_source=gs('algorithms.op.paths.weighted#o06', 'it66 R1-CB-05 split: native half -> new row'))
add('algorithms.op.paths.weighted#o06', SPLIT, locator="bullet 3: 'The native search also treats negative hops as unbounded'",
    statement='The native search treats a negative hop limit as unbounded', cases='native maxHops -1 finds a 7-hop path',
    observation='native rows', gap='tBound = (+maxHops > 0) makes a negative limit unbounded natively; the model\'s bound is a nat, so the negative case is not representable',
    grade_source='new (it66 split of algorithms.op.paths.weighted#o06)')
setc('algorithms.op.paths.weighted#o08', 'R1-CB-05 split (named): Python refusal vs native outcome', grade='absent',
     statement='The public procedure refuses an empty or missing endpoint argument', cases="('',b) through the public procedure: error",
     observation='error', model_locators='', design_check='none', check_scope='n/a', design_receipts='',
     gap='the public refusal is outside the formal domain (sql_procs and weighted_paths model the native search)',
     grade_source=gs('algorithms.op.paths.weighted#o08', 'it66 R1-CB-05 split: o08 keeps the public refusal (absent); the native no-path half -> new row (full)'))
add('algorithms.op.paths.weighted#o08', SPLIT, locator="bullet 4: 'direct native empty endpoints answer no path'",
    statement='A direct native search with an empty endpoint answers no path', cases="native DijkstraJson('',b): {} vs (a,b) connected: a path",
    observation='native JSON', grade='full', design_check='proved', check_scope='narrowed',
    model_locators=loc('sql_procs', 'theorem_dijkstra_endpoint_neighbors') + '; ' + loc('weighted_paths', 'theorem_empty_queue_is_no_feasible_path'),
    design_receipts=prove('sql_procs') + '; ' + prove('weighted_paths'), premises="'' arrives as $Char(0), which has no edges; composition through weighted_paths' empty-queue theorem",
    gap=NOGAP, grade_source='new (it66 split of algorithms.op.paths.weighted#o08)')

# search.fusion.python#o04
setc('search.fusion.python#o04', 'R1-CB-05 split: one row per entity -> new row', statement='The result is in descending fused score',
     cases='a above b in fused score -> a first',
     grade_source=gs('search.fusion.python#o04', 'it66 R1-CB-05 split: de-duplication -> new row'))
add('search.fusion.python#o04', SPLIT, locator="lead: 'returns each entity once'", statement='The fused result lists each entity once',
    cases='entity in both lists -> one row', grade='absent', model_locators='', design_check='none', check_scope='n/a', design_receipts='',
    gap='de-duplication observed in Python only (fusion_ranking NOTES)', grade_source='new (it66 split of search.fusion.python#o04)')

# install.status.capabilities#o02
OR = 'operator_reports'
setc('install.status.capabilities#o02', 'R1-CB-05 split: three separately decided outcomes',
     statement='Each engine detects its capabilities once', cases='detection repeated on one engine -> the first answer',
     locator="lead: 'Each engine reads it once'", model_locators=loc(OR, 'caps_of') + '; ' + loc(OR, 'detect'),
     design_check='none', check_scope='n/a', design_receipts='',
     gap="once-per-engine caching holds by caps_of's definition; no theorem",
     grade_source=gs('install.status.capabilities#o02', 'it66 R1-CB-05 split: class dictionary and markers -> new rows'))
add('install.status.capabilities#o02', SPLIT, locator="lead: 'from the class dictionary'",
    statement='Capability detection reads the deployed classes from the class dictionary', cases='class compiled vs not -> os capability',
    model_locators=loc(OR, 'detect'), grade='partial', design_check='none', check_scope='n/a', design_receipts='',
    gap='the class-dictionary probe is a constant (os true) in detect; not modelled',
    grade_source='new (it66 split of install.status.capabilities#o02)')
add('install.status.capabilities#o02', SPLIT, locator="lead: 'two markers that setup writes when it finds edge rows to build from'",
    statement='Setup writes the two Meta markers only when it finds edge rows to build from', cases='setup with vs without edge rows',
    model_locators=loc(OR, 'theorem_setup_with_edges_sets_markers') + '; ' + loc(OR, 'theorem_markers_never_set_after_empty_setup'),
    grade='full', design_check='proved', check_scope='narrowed', design_receipts=prove(OR), gap=NOGAP,
    grade_source='new (it66 split of install.status.capabilities#o02)')

# ----------------------------------------------------------------------------------------------------------------
# 3. R1-CB-05 sweep splits (sweep/decisions.tsv records every flagged row's decision)
def split2(oid, first, rest, note=''):
    """first: column changes for the original; rest: list of column dicts for new rows."""
    setc(oid, 'R1-CB-05 sweep split' + (': ' + note if note else ''), **first,
         grade_source=gs(oid, 'it66 R1-CB-05 sweep split' + (' (' + note + ')' if note else '')))
    for cols in rest:
        add(oid, SPLIT, grade_source=f'new (it66 sweep split of {oid})', **cols)

ABS = dict(grade='absent', model_locators='', design_check='none', check_scope='n/a', design_receipts='')
split2('query.paths#o01',
       dict(statement='A query the native executor does not support (or declines) is answered by the SQL path exactly as with the native executor off',
            cases='unsupported read vs write, each with native on and off'),
       [dict(locator="lead: 'Every Cypher query has a SQL-path answer'", statement='Every Cypher query the product accepts has a SQL-path answer',
             cases='supported read, unsupported read and write each answered with native off',
             gap="the SQL path's answer is a world input (sql_out); no model of the translator's coverage")])
split2('access.bolt.errors#o01',
       dict(statement='A failed RUN answers FAILURE with a status code and the failure text', cases='failing RUN -> FAILURE {code, message}',
            gap="bolt_stream's Answer::Failure carries neither the Neo4j status code nor the failure's text; the code is bolt_answers' separate classification bolt_code and the text is not modelled"),
       [dict(locator="'RESET then a new RUN succeeds'", statement='After a failed RUN, RESET then a new RUN succeeds',
             cases='failing RUN, RESET, RUN: success vs failing RUN, RUN: IGNORED', grade='full',
             model_locators=loc('bolt_stream', 'theorem_reset_allows_next_result') + '; ' + loc('bolt_stream', 'theorem_error_produces_failure_and_failed_gate'),
             design_receipts=prove('bolt_stream'), gap=NOGAP)])
split2('ledger.commit.caller-transaction#o06',
       dict(statement="A written, replayed or counted-refusal commit inside a caller's transaction holds the counter row to transaction end; meanwhile another connection's refused commit is not counted",
            cases='caller commit open: other\'s lock timeout counter +0 vs after caller commit: counted'),
       [dict(locator="'a strict-mode count made elsewhere is lost'", statement="While a caller's transaction holds the counter row, a strict-mode refusal count made by another connection is lost",
             cases='row held by r != p: count_strict leaves the counters; row free: strict_block +1', grade='full',
             model_locators=loc('ledger_client', 'theorem_uncounted_outcomes'), gap=NOGAP)])
split2('ledger.readers.history#o09',
       dict(statement='A history read with limit 0 returns empty', cases='limit 0: [] vs limit 1: one revision'),
       [dict(locator="'negative limit is refused by IRIS'", statement='A history read with a negative limit is refused (by IRIS)',
             cases='limit -1: error vs 0: []')], 'Python vs IRIS decider')
split2('redaction.target.nodes#o03',
       dict(statement="A relationship delete or detach delete inside a tenant's revision writes delete records for the relationship's reifier nodes, with the reifier's own ID and the default graph",
            cases='relationship deleted with vs without reifiers', **ABS,
            gap='the producer (LedgerApply.DeleteRelInternal / DeleteNodeRows writing reifier delete records into the tenant\'s revision) is not modelled and no witness or native case exists (bug-led-005, suspected)'),
       [dict(locator="'unless the reifier ID begins with the tenant's prefix, neither ... tombstones them'",
             statement="Unless a reifier's ID begins with the tenant's prefix, neither the tenant's graph target nor its prefix target tombstones its delete record",
             cases='reifier id with vs without the tenant prefix', premises='the reifier delete record exists (producer not modelled)',
             grade='partial', model_locators='.g5/Verus_verification/models/ledger_redaction/redaction.rs::matches',
             gap='the classification follows from matches (a spec fn) once the record exists; no theorem or witness')], 'record writer vs redaction selection')
split2('ledger.lifecycle#o03',
       dict(statement='The first enable fixes max_ops and recon_bound and sets strict', model_locators=loc('ledger_client', 'theorem_enable_lifecycle')),
       [dict(locator="'set_strict switches strict later'", statement='set_strict switches strict mode on an enabled ledger later',
             cases='set_strict(True) after enable: strict on', model_locators=loc('ledger_client', 'theorem_disable_and_set_strict'))], 'two entry points')
lcp_ = prove('ledger_client')
split2('ledger.lifecycle#o08',
       dict(statement='Before the first enable, commit refuses LedgerNotEnabledError', cases='never enabled: commit refused vs disabled: LedgerDisabledError',
            model_locators=loc('ledger_client', 'theorem_disabled_and_never_enabled'), grade='full', gap=NOGAP),
       [dict(locator="'head'", statement='Before the first enable, head() refuses LedgerNotEnabledError', cases='never enabled: refused vs disabled: answered',
             model_locators=loc('ledger_client', 'theorem_head_reader_states'), grade='full', gap=NOGAP),
        dict(locator="'set_strict'", statement='Before the first enable, set_strict refuses LedgerNotEnabledError', cases='never enabled: refused vs disabled: set',
             model_locators=loc('ledger_client', 'theorem_disable_and_set_strict'), grade='full', gap=NOGAP),
        dict(locator="'redact'", statement='Before the first enable, redact refuses LedgerNotEnabledError', cases='never enabled: refused', **ABS,
             gap='redaction start before enable is not represented'),
        dict(locator="'verify'", statement='Before the first enable, verify refuses LedgerNotEnabledError', cases='never enabled: refused', **ABS,
             gap='verify before enable is not represented'),
        dict(locator="'history is empty'", statement='Before the first enable, history is empty', cases='never enabled: history []', **ABS,
             gap="'history is empty' before enable is not represented")], 'five entry points and a reader')
split2('ledger.verify#o04',
       dict(statement='A tables-only entity is reported with its attributes', cases='unrecorded node with label+property: 3 entries',
            model_locators=loc('ledger_verify', 'theorem_entries_for_created_and_deleted_nodes')),
       [dict(locator="'a history-only entity is one deletion entry whose adoption also removes its attributes'",
             statement='A history-only entity is reported as one deletion entry whose adoption also removes its attributes',
             cases='history-only node: 1 deletion; adopted -> its labels and properties gone')], 'report vs adoption')
split2('ledger.verify.scope#o05',
       dict(statement='The tables view leaves out relationship rows whose qualifier temporal is the JSON boolean true',
            cases="JSON true row: out of tables, text 'true' row: kept",
            model_locators=loc('ledger_verify', 'theorem_temporal_marked_rows_left_out') + '; ' + loc('ledger_verify', 'theorem_marker_rules_differ')),
       [dict(locator="'The replay leaves out a recorded relationship whose qualifier temporal is the text \"true\"'",
             statement="The replay leaves out recorded relationships whose qualifier temporal is the text 'true'",
             cases="replay text 'true': out, 'yes': kept",
             model_locators=loc('ledger_verify', 'lemma_replay_view_dropped') + '; ' + loc('ledger_verify', 'theorem_marker_rules_differ'))], 'two readers')
TS = 'traversal_strategy'
split2('structure.adjacency#o04',
       dict(statement="The BFS walk and its SQL fallback each answer from one graph's entries; edges in another graph change no answer",
            cases='same s,p,o added in graph h vs not, walking graph g -> same answer for both readers', grade='full', gap=NOGAP),
       [dict(locator="'the ends-only walk'", statement="The ends-only walk (VarLength.Ends) answers from one graph's entries",
             cases='edge added in graph h vs not -> same ends in g', model_locators=loc(TS, 'vl_end'), design_check='none', check_scope='n/a',
             design_receipts='', grade='partial', gap="vl_end reads q.g's edges by definition; no theorem states the graph confinement"),
        dict(locator="'and the shortest-path routines'", statement="The shortest-path routines answer from one graph's entries",
             cases='edge added in graph h vs not -> same shortest path in g',
             model_locators=loc(TS, 'esp_len') + '; ' + loc('weighted_paths', 'theorem_complete_terminating_search'),
             design_check='none', check_scope='n/a', design_receipts='', grade='partial',
             gap='the weighted search is graph-scoped (algorithms.op.paths.weighted#o09); the unweighted ShortestPathJson / ShortestLength confinement is esp_len\'s definition only')],
       'four named readers; the BFS pair keeps the proved theorems')
undec = byid['structure.adjacency.undeclared#o03']
split2('structure.adjacency.undeclared#o03',
       dict(statement='Without the declared index, Cypher writes change rows but not the adjacency index, which stays stale until a rebuild',
            cases='Cypher CREATE in an undeclared namespace -> row without entry; the same write declared -> entry follows',
            gap='the witness is a raw SQL delete; the Cypher writer is not distinguished'),
       [dict(locator="'store_edge'", statement='Without the declared index, store_edge changes rows but not the adjacency index',
             cases='store_edge undeclared -> row without entry', gap='the witness is a raw SQL delete; store_edge is not distinguished'),
        dict(locator="'and the store's write_edges'", statement="Without the declared index, the store's write_edges changes rows but not the adjacency index",
             cases='write_edges undeclared -> rows without entries', gap='the witness is a raw SQL delete; write_edges is not distinguished')],
       'three writers')
split2('structure.adjacency.bulk#o02',
       dict(statement='bulk_create_nodes, having dropped the indexes for a large batch, rebuilds them before returning, on success and on failure'),
       [dict(statement='bulk_create_edges, having dropped the indexes for a large batch, rebuilds them before returning, on success and on failure',
             locator="'bulk_create_edges'")], 'two entry points')
split2('structure.degree.cache.warm#o03',
       dict(statement='WarmAll fills the all-predicate entry and each predicate entry of each source and returns the number of sources filled, not entries',
            cases='one source with two predicates -> 3 entries, return 1', gap='one-source theorem'),
       [dict(locator="'target-only nodes are not sources'", statement='WarmAll does not treat target-only nodes as sources',
             cases='a target-only node -> not filled, not counted', design_check='none', check_scope='n/a', design_receipts='',
             gap='the visited source sequence is an input (enumeration completeness premise), so the exclusion is not derived')], 'enumeration vs fill')
split2('temporal.stats.writers#o04',
       dict(statement="A delete recomputes the bucket's count and minimum from the surviving edges",
            cases='two edges, delete one -> count and minimum of the survivor', grade='full', gap=NOGAP,
            model_locators=loc('temporal_stats', 'theorem_delete_rebuilds_from_survivors')),
       [dict(locator="'sum, extremes and sketch'", statement="A delete recomputes the bucket's sum, maximum and sketch from the surviving edges",
             cases='two edges, delete one -> sum, maximum and sketch of the survivor',
             model_locators=loc('temporal_stats', 'delete_at') + '; ' + loc('temporal_stats', 'rebuild'), design_check='none', check_scope='n/a',
             design_receipts='', grade='partial', gap='rebuild/delete_at definitions; no theorem concludes them'),
        dict(locator="'lowers the event counter by one, removing it at zero'", statement='A delete lowers the event counter by one and removes it at zero',
             cases='delete one of two -> counter -1; delete last -> counter gone; update then delete -> counter 1 with no edge',
             model_locators=loc('temporal_stats', 'delete_at') + '; ' + loc('temporal_stats', 'theorem_update_then_delete_leaves_velocity'), grade='partial',
             gap='the counter at zero is removed by delete_at\'s definition; theorem_update_then_delete_leaves_velocity covers the update-then-delete residue only')],
       'three separately written stores')
split2('search.quarantine#o08', dict(statement='Unplaceable documents go to their own quarantine table'),
       [dict(statement='Unplaceable edge vectors go to their own quarantine table', locator="'and edge vectors'"),
        dict(statement='No API places a quarantined document or edge vector', locator="'no API places them'", cases='quarantined row: no placement call exists')],
       'two writers and a missing API')
split2('algorithms.op.pagerank#o04', dict(statement='PageRank defaults to damping 0.85 and 20 iterations', cases='call with no options -> 0.85, 20'),
       [dict(statement='The PageRank Owner runs exactly the iteration count, while the Arno reader may stop earlier once converged',
             locator="'the Owner runs exactly the iteration count'", cases='Owner at 20 iterations vs Arno converged answer')], 'defaults vs iteration behaviour')
PP = 'ppr_walk'
split2('algorithms.op.ppr#o05',
       dict(statement='PPR seeds are deduplicated', cases='seeds [a,a]: a gets the whole share vs 1/2 twice',
            model_locators=loc(PP, 'theorem_valid_seed_set'), design_receipts=prove(PP) + '; ' + ctl(PP, 'repeated-seeds-count-twice'), gap=NOGAP),
       [dict(locator="'a seed that is not a node of the graph contributes nothing'", statement='A PPR seed that is not a node of the graph contributes nothing',
             cases='seeds [a, ghost]: ghost absent, a gets the whole share',
             model_locators=loc(PP, 'theorem_valid_seed_set') + '; ' + loc(PP, 'theorem_no_valid_seed_is_empty'),
             design_receipts=prove(PP) + '; ' + ctl(PP, 'absent-seed-admitted'), gap=NOGAP),
        dict(locator="'unreached nodes are listed at 0.0'", statement='PPR lists unreached nodes at 0.0', cases='unreached c present at 0.0',
             model_locators=loc(PP, 'theorem_positive_rank_and_zeros_read_together') + '; ' + loc(PP, 'lemma_missing_rows'),
             design_receipts=prove(PP) + '; ' + ctl(PP, 'zero-completion-removed'))], 'three outcomes, each with its own control')
split2('algorithms.op.betweenness#o06', dict(statement='Betweenness with out/in scores the directed graph and with both the undirected graph', cases='both vs out on a->b->c'),
       [dict(statement='Betweenness with max_hops=k counts only pairs within k hops', locator="'max_hops=k counts only pairs within k hops'", cases='max_hops 1 vs 0')],
       'two options')
split2('algorithms.op.leiden#o04', dict(statement='Leiden rows are {id, community, size} with community 0 the largest', cases='two communities -> the larger is 0'),
       [dict(statement='Leiden top_k cuts rows, possibly through a community', locator="'top_k cuts rows, possibly through a community'",
             cases='top_k smaller than the largest community')], 'shape vs cut')
split2('algorithms.op.paths#o02', dict(statement='A shortest-path call with equal endpoints answers length 0', cases='(a,a): 0 vs (a,b): search'),
       [dict(statement='A shortest-path call with an empty endpoint answers no path', locator="'an empty endpoint answers no path'",
             cases="('',b): no path", **ABS, gap='empty endpoints not modelled')], 'two guards')
split2('query.paths.varlength#o01',
       dict(statement='On the SQL path a Cypher variable-length pattern returns one row per path (openCypher multiplicity): over a->x->b, a->y->b, a->b, *1..2 gives b three times and x, y once; *2..2 gives b twice; *0..1 includes a',
            cases='*1..2 vs *2..2 vs *0..1 on the fixture, native off'),
       [dict(statement='On the native executor a Cypher variable-length pattern returns one row per path (openCypher multiplicity), as on the SQL path',
             locator="'on the native and SQL paths'", cases='*1..2 vs *2..2 vs *0..1 on the fixture, native on')], 'two executors')
CC = 'cypher_clauses'
split2('query.aggregation.keys#o03',
       dict(statement='SQL path: grouping keys and count(DISTINCT) merge a stored number with its spelling', grade='full',
            cases="1 and '1' under GROUP BY and count(DISTINCT) -> one group / one count",
            model_locators=loc(CC, 'theorem_sql_group_merges_number_and_its_text'), gap=NOGAP),
       [dict(locator="'(key reads as one of them)'", statement='SQL path: a merged group\'s key reads as one of the merged values', cases="1 and '1' grouped -> key 1 or '1'",
             **ABS, gap='which representative the key reads as is not modelled'),
        dict(locator="'and WITH DISTINCT'", statement='SQL path: WITH DISTINCT merges a stored number with its spelling', cases="1 and '1' under WITH DISTINCT -> one row",
             **ABS, gap='WITH DISTINCT is not modelled'),
        dict(locator="'RETURN DISTINCT ... keep them apart'", statement='SQL path: RETURN DISTINCT keeps a stored number and its spelling apart', grade='full',
             cases="1 and '1' under RETURN DISTINCT -> two rows",
             model_locators=loc(CC, 'theorem_sql_return_distinct_keeps_kinds') + '; ' + loc(CC, 'theorem_sql_group_and_distinct_disagree_on_marked_text'), gap=NOGAP),
        dict(locator="'and collect(DISTINCT) keep them apart'", statement='SQL path: collect(DISTINCT) keeps a stored number and its spelling apart',
             cases="collect(DISTINCT) over 1 and '1' -> two elements", **ABS, gap='collect(DISTINCT) is not modelled')],
       'five constructs, each translated separately')
split2('query.aggregation.keys#o07',
       dict(statement='SQL path: stored 1 and 1.0 are one value for grouping and count(DISTINCT) but two for RETURN DISTINCT',
            cases='stored 1/1.0 under GROUP, count(DISTINCT), RETURN DISTINCT',
            gap='only count(DISTINCT) normalization is proved (over the SQLite provider); grouping and RETURN DISTINCT are not modeled'),
       [dict(locator="'over a held list RETURN DISTINCT and UNION make them one row'", statement='Over a held list, RETURN DISTINCT and UNION make 1 and 1.0 one row',
             cases='UNWIND [1,1.0] RETURN DISTINCT; RETURN 1 UNION RETURN 1.0', **ABS, gap='held-list DISTINCT and UNION over floats are not modelled')],
       'stored vs held list')
split2('query.optional#o14',
       dict(statement='A property of an unbound node is null at the four readers and both drivers, also through WITH', cases='b.x unbound vs bound; through WITH',
            gap="the decoder's null pass-through has no control (AUDIT row 20)"),
       [dict(locator="'collect() of the unbound node is []'", statement='collect() of an unbound OPTIONAL node is []', cases='collect(b) unbound -> []',
             **ABS, gap='collect() of an unbound node is not modeled')], 'property read vs aggregate')
split2('query.optional#o15',
       dict(statement="An unbound node answers b_id null and b_labels '[]' at execute_cypher, /api/cypher and tx/commit; Bolt answers null",
            gap="b_id null is not stated by theorem_optional_node_labels (labels column only)"),
       [dict(locator="'b_props ... '[]''", statement="An unbound node answers b_props '[]' at execute_cypher, /api/cypher and tx/commit",
             cases='unbound node at the three readers', **ABS, gap="b_props '[]' is not modeled")], 'separately produced columns')
split2('query.parameters#o01',
       dict(statement='Wherever a literal is allowed, a parameter of the same value and type gives the same answer at execute_cypher'),
       [dict(locator="'Bolt'", statement='Wherever a literal is allowed, a parameter of the same value and type gives the same answer through Bolt'),
        dict(locator="'and HTTP'", statement='Wherever a literal is allowed, a parameter of the same value and type gives the same answer through HTTP')],
       'three entry points with their own parameter decoding')
split2('query.values.equality#o05',
       dict(statement='A relationship whole float 1.0 equals 1 but not true', cases='1.0 on a relationship against 1 and true'),
       [dict(locator="'a node double 1.0 equals both'", statement='A node double 1.0 equals both 1 and true', cases='1.0 on a node against 1 and true',
             **ABS, gap='no theorem states the node-double/true case')], 'two stores')
split2('fhir.graph#o01', dict(statement='A registered repository is projected into its own named graph fhir:<namespace>:<package>, never the default graph',
                              cases='register in namespace NS package P -> graph fhir:NS:P'),
       [dict(locator="'a FHIR graph call without a graph id refuses'", statement='A FHIR graph call without a graph id refuses',
             cases="fhir_graph_sync(None or '') -> ValueError, nothing read")], 'naming vs refusal')
FT = 'fhir_tasks'
split2('fhir.graph.lifecycle#o03',
       dict(statement='FHIR graph status reports the task id', cases='scheduled -> task_id; unscheduled -> none',
            gap='status is a task_id/interval/version point projection'),
       [dict(locator="'node, reference-edge and compartment-edge counts'", statement="FHIR graph status reports the graph's node, reference-edge and compartment-edge counts",
             cases='after a sync with 3 new rows -> counts updated', **ABS, gap='counts unmodelled (NOTES: full counts / FHIR LoadColumns unproved)'),
        dict(locator="'pending changes past the watermarks'", statement='FHIR graph status reports the pending changes past the watermarks',
             cases='after a sync -> pending 0; one new resource -> pending 1', **ABS, gap='pending unmodelled'),
        dict(locator="'last sync and rebuild, last error'", statement='FHIR graph status reports the last sync, last rebuild and last error',
             cases='failed batch -> last_error set', **ABS, gap='last_sync/last_rebuild/last_error unmodelled')], 'separately computed fields')
split2('structure.node.bulk#o08', dict(statement='bulk_create_nodes does not write None-valued properties', cases='property None -> not written'),
       [dict(locator="'id defaults to the node ID when absent; an explicit None id writes no id'",
             statement='bulk_create_nodes defaults the id property to the node ID when absent; an explicit None id writes no id', cases='absent id vs id None vs id given')],
       'two rules')
split2('search.ivf#o02', dict(statement="After a build, ivf_insert/ivf_delete change one node's entries", cases='insert then delete a new node -> index as before',
                              grade='full', gap=NOGAP),
       [dict(locator="'a rebuild replaces the index with the route's current vectors'", statement="An IVF rebuild replaces the index with the route's current vectors",
             cases="rebuild after route changes -> route's vectors only", **ABS, gap='rebuild observed (W52) but not modeled')], 'two entry points')
split2('search.ivf#o03', dict(statement='Searching an absent node or an unbuilt IVF index answers no hit and no error', cases='unbuilt index search -> [] no error'),
       [dict(locator="'inserting into a missing index is refused'", statement='Inserting into a missing IVF index is refused', cases='insert into missing -> error')],
       'search vs insert')
split2('search.fusion.vector_graph#o06', dict(statement='kg_VECTOR_GRAPH_SEARCH with a wrong-width query raises', cases='3-wide query on 4-wide route -> error',
                                              model_locators=loc('vector_admission', 'theorem_preflight_derived_mismatch')),
       [dict(locator="'a graph without vectors answers nothing'", statement='kg_VECTOR_GRAPH_SEARCH over a graph without vectors answers nothing',
             cases='graph without route -> []', model_locators=loc('vector_admission', 'theorem_whole_missing_raw_pair_returns_quiet_empty'))], 'two guards')
split2('search.fusion.multi_vector#o01', dict(statement='multi_vector_search fetches 2 x top_k rows per source', cases='top_k 5 -> 10 rows per source',
                                              gap='mvs_rows is a definition; no theorem'),
       [dict(locator="'fuses by sum of weight/(rrf_k + rank)'", statement="multi_vector_search with fusion 'rrf' fuses by the sum of weight/(rrf_k + rank)",
             cases="fusion='rrf' with weights -> weighted RRF", **ABS, gap='weighted fusion observed (M1-M3), not represented'),
        dict(locator="'any other fusion value ranks by raw score ignoring weights'", statement='multi_vector_search with any other fusion value ranks by raw score, ignoring weights',
             cases="fusion='max' -> raw score, weights ignored", **ABS, gap='raw-score branch observed (M1-M3), not represented')], 'three rules')
TST = 'temporal_stats'
split2('temporal.edge#o05', dict(statement='The time unit is set by the entry point (engine: seconds; TemporalIndexMS: milliseconds)',
                                 cases='engine write -> seconds class; TemporalIndexMS -> milliseconds', design_check='none', check_scope='n/a', design_receipts='',
                                 model_locators=loc(TST, 'theorem_ms_edge_in_seconds_whole_bucket'),
                                 gap='the entry-point-to-unit mapping is an input (bucket divisor 300 vs 300000); that the engine calls only the seconds class is inspection'),
       [dict(locator="'a bucket is five minutes in either unit'", statement='A temporal bucket is five minutes in either unit',
             cases='event at x seconds via the seconds class vs x*1000 via the ms class -> same bucket key', grade='full', gap=NOGAP,
             design_check='proved', check_scope='narrowed', design_receipts=prove(TST))],
       'unit choice vs bucket width')
split2('temporal.stats.window#o13',
       dict(statement='A millisecond-class edge is counted by the seconds whole-bucket counts', cases='ms-class event at x*1000 -> whole-bucket count 1', grade='full', gap=NOGAP),
       [dict(locator="'but not by ... edge-by-edge reads'", statement='A millisecond-class edge is not counted by the seconds edge-by-edge (raw window) reads',
             cases='ms-class event at x*1000 -> raw window count 0', grade='full', gap=NOGAP),
        dict(locator="'groups'", statement='A millisecond-class edge is counted by the seconds group reads', cases='ms-class event -> its group counted',
             **ABS, gap='group reads are not stated by any theorem'),
        dict(locator="'velocity'", statement='A millisecond-class edge is counted by the seconds velocity read', cases='ms-class event -> velocity counts it',
             **ABS, gap='velocity is binding-only'),
        dict(locator="'distinct estimates'", statement='A millisecond-class edge is counted by the seconds distinct estimates', cases='ms-class event -> distinct estimate counts it',
             **ABS, gap='distinct estimates are not stated'),
        dict(locator="'but not by target reads'", statement='A millisecond-class edge is not counted by the seconds target reads', cases='ms-class event -> target read 0',
             **ABS, gap='target reads are not stated'),
        dict(locator="'or cut windows'", statement='A millisecond-class edge is not counted by seconds cut windows', cases='ms-class event in a cut window -> 0',
             grade='partial', design_check='none', check_scope='n/a', design_receipts='', model_locators=loc(TST, 'raw_agg'),
             gap="a cut window reads raw_agg at its edges (definition); no theorem states the cut-window reader")],
       'seven readers, each separately implemented')
split2('temporal.purge.bare-nodes#o04', dict(statement='Python temporal purges retire bare nodes by default', cases='Python purge default -> bare nodes retired'),
       [dict(locator="'ObjectScript purges only when asked'", statement='ObjectScript temporal purges retire bare nodes only when asked', cases='ObjectScript default -> kept')],
       'two entry points')
split2('install.bulk_load.rebuild#o02', dict(statement='An index a bulk load dropped and could not rebuild is named in a warning', cases='rebuild failure -> warning naming it'),
       [dict(locator="'reads needing it still answer by scanning'", statement='After a failed post-load index rebuild, reads needing the index still answer by scanning',
             cases='rebuild failure -> reads answer', gap='no model')], 'warning vs reads')
setc('search.fusion.surfaces#o06', 'R1-CB-03 / LINT-4 (no model item) and R1-CB-05 sweep split (three entry points)', **ABS,
     statement='The engine method kg_RRF_FUSE takes c with no default', cases='kg_RRF_FUSE without c -> TypeError',
     gap='the defaults are bound as delegating members in the binding; not represented in retrieval_compose (c is a parameter)',
     grade_source=gs('search.fusion.surfaces#o06', 'it66 LINT-4: partial -> absent (no model locator); R1-CB-05 sweep split'))
add('search.fusion.surfaces#o06', SPLIT, locator="'IRISGraphOperators and kg_RERANK use 60'", statement='IRISGraphOperators and kg_RERANK default c to 60',
    cases='kg_RERANK without c -> c 60', grade_source='new (it66 sweep split of search.fusion.surfaces#o06)')
add('search.fusion.surfaces#o06', SPLIT, locator="'kg_RERANK searches each leg 2 x top_n deep'", statement='kg_RERANK searches each leg 2 x top_n deep',
    cases='kg_RERANK(top_n=5) -> legs of 10', grade_source='new (it66 sweep split of search.fusion.surfaces#o06)')

# ----------------------------------------------------------------------------------------------------------------
# 4. Re-search of rows graded before iteration 65 against native_admission (it62) and erasure_stores (it65)
#    (research-decisions.tsv lists every candidate; the changes are here)
ES = 'erasure_stores'
esp, esb = prove(ES), 'binding AGREES ' + bind(ES)
RS = 'it66 re-search (review-1): '
r = byid['graph.key#o02']
setc('graph.key#o02', RS + 'erasure_stores refutes the clearing half as built; split (visit locality vs change)',
     statement="Clearing one graph changes no other graph's entries",
     cases="erase g: an entry of graph h (same IDs) unchanged; ^IVG.AlgoCache(h, ...) after erase_graph(g)",
     model_locators=r['model_locators'] + '; ' + loc(ES, 'theorem_erase_clears_algo_cache') + '; ' + loc(ES, 'theorem_graph_erase_frame'),
     premises='adjacency writers; erase in the redaction model; erasure_stores: every entry point of the Eraser',
     grade='full', design_check='refuted', check_scope='narrowed', design_receipts=r['design_receipts'] + '; ' + esp,
     as_built=(r['as_built'] + '; ' if r['as_built'] not in ('', 'none') else '') + esb,
     gap=NOGAP,
     grade_source=gs('graph.key#o02', 'it66 re-search: refuted as built by erasure_stores theorem_erase_clears_algo_cache (a graph erase kills ^IVG.AlgoCache for every graph, bug-str-118; live B1); every other graph-scoped kind is kept (theorem_graph_erase_frame); split: visit locality -> new row'))
add('graph.key#o02', SPLIT + '; re-search', locator=r['locator'], statement="Reading or clearing one graph visits no other graph's subtree",
    cases='read/clear g with a large graph h present -> h not scanned', **ABS,
    gap='the locality (no visit or scan of other graphs) is not represented', grade_source='new (it66 split of graph.key#o02)')
setc('search.routes.orphan#o02', RS + 'erasure_stores theorem_graph_erase_routes', grade='full', design_check='proved', check_scope='full',
     model_locators=loc(ES, 'theorem_graph_erase_routes'), design_receipts=esp, as_built=esb,
     premises='requires-reviewed: 0 <= i < len and the entry being a route row, route table or registry row only select the entry the statement is about',
     gap=NOGAP, grade_source=gs('search.routes.orphan#o02', 'it66 re-search: absent -> full (NRoute rows of g removed; an unclaimed (orphan) RouteTable kept; live B1 orphan route)'))
setc('fhir.interpretation#o04', RS + 'compartment edges are ordinary edge rows of the FHIR graph', grade='full', design_check='proved', check_scope='narrowed',
     model_locators=loc(ES, 'theorem_graph_erase_removes_scoped'), design_receipts=esp, as_built=esb,
     premises='compartment edges are rdf_edges rows of the FHIR graph (the projection writes them as ordinary edges); EraseGraph removes every Edge entry of the graph',
     gap=NOGAP, grade_source=gs('fhir.interpretation#o04', 'it66 re-search: absent -> full (erasure_stores graph_kill(Edge))'))
setc('structure.edge.delete#o06', RS + 'erasure_stores witness_delete_edge_leaves_statement', grade='full', design_check='proved', check_scope='narrowed',
     model_locators=loc(ES, 'witness_delete_edge_leaves_statement'), design_receipts=esp, as_built=esb,
     premises='point witness of the as-built delete_edge bypass (one edge, its statement, reification and edge vector)',
     gap=NOGAP, grade_source=gs('structure.edge.delete#o06', 'it66 re-search: absent -> full (edge row and adjacency removed; statement, reification and edge vector kept; live C7)'))
r = byid['temporal.erase#o01']
setc('temporal.erase#o01', RS + 'erasure_stores theorem_ids_erase', grade='full', design_check='proved', check_scope='narrowed',
     model_locators=r['model_locators'] + '; ' + loc(ES, 'theorem_ids_erase'), design_receipts=esp, as_built=esb,
     premises='the temporal subtrees are one entry kind per (graph, source, target) in erasure_stores; EraseNodeIds is the node-erase entry',
     gap=NOGAP, grade_source=gs('temporal.erase#o01', 'it66 re-search: partial -> full (Temporal entries of c with the node as source or target removed; other graphs kept)'))
for oid, what in (('temporal.latest.exact#o04', 'node'), ('temporal.latest.exact#o05', 'graph')):
    setc(oid, RS + 'erasure_stores represents the removal, not the exactness', grade='partial',
         model_locators=loc(ES, 'theorem_ids_erase' if what == 'node' else 'theorem_graph_erase_removes_scoped'),
         gap=f'erasure_stores lumps tlast into the Temporal kind: the {what} erase removes its entries and keeps other graphs\', but the newest-event index\'s exactness for the surviving events is not represented',
         grade_source=gs(oid, 'it66 re-search: absent -> partial'))
setc('structure.node.delete#o02', RS + 'EraseNodeIds removes the IDs\' documents and vectors in the graph', grade='partial',
     model_locators=loc(ES, 'theorem_ids_erase') + '; ' + loc(ES, 'theorem_methods_reach_eraser'),
     gap='theorem_ids_erase removes Doc, NEmb and routed rows of the IDs in c; delete_node -> EraseNodeIds is a constant table (review-1 R1-ER-03) and delete_node\'s reifier step is outside it (R1-ER-01)',
     grade_source=gs('structure.node.delete#o02', 'it66 re-search: absent -> partial'))
setc('structure.node.delete#o04', RS + 'the one-transaction outcome is the model\'s definition', grade='partial',
     model_locators=loc(ES, 'theorem_failed_call_leaves_stores'),
     gap='erasure_stores defines a failed call as leaving the stores unchanged (review-1 R1-ER-02: true by definition), so all-or-none is not derived from a failing step',
     grade_source=gs('structure.node.delete#o04', 'it66 re-search: absent -> partial'))
setc('structure.node.delete.bulk#o06', RS + 'the chunk commit is modelled; the batch count is not composed', grade='partial',
     model_locators=loc(ES, 'witness_list_erase_commits_earlier_chunk'),
     gap='erasure_stores witnesses the earlier chunk committing (live E4); bulk_delete_nodes\' failed count and log are not composed with it',
     grade_source=gs('structure.node.delete.bulk#o06', 'it66 re-search: absent -> partial'))
setc('structure.rebuilt.stale_read#o02', RS + 'the model reaches the dropped snapshot, not the reader', grade='partial',
     model_locators=loc(ES, 'witness_graph_erase_drops_unscoped_nkg'),
     gap='erasure_stores shows an erase dropping ^NKG; the first reader\'s rebuild under a lock (EnsureNKG) is not modelled',
     grade_source=gs('structure.rebuilt.stale_read#o02', 'it66 re-search: absent -> partial (stops before the reader)'))
setc('search.scope.indexes.upkeep#o02', RS + 'no erase entry point touches the named indexes', grade='partial',
     model_locators=loc(ES, 'theorem_no_erase_touches_kind'),
     gap="theorem_no_erase_touches_kind keeps ^BM25Idx/^IVF/^PLAID/^VecIdx under every erase entry point (incl. EraseNodeIds); the index reader and 'until the caller deletes it or rebuilds' are not modelled; delete_node -> EraseNodeIds is a constant table (R1-ER-03)",
     grade_source=gs('search.scope.indexes.upkeep#o02', 'it66 re-search: absent -> partial'))
for oid, item, note in (('install.snapshot.scope#o02', 'theorem_erase_all_empties', 'erase_all empties every store (the replacing restore\'s first step)'),
                        ('install.status.sync#o05', 'witness_graph_erase_drops_unscoped_nkg', 'the erase dropping ^NKG'),
                        ('graph.key.two_forms#o03', 'theorem_default_graph_both_spellings', 'the Eraser as one more SQL writer taking NULL and \'\' as the default graph')):
    setc(oid, RS + 'locator added; grade held', model_locators=byid[oid]['model_locators'] + '; ' + loc(ES, item),
         grade_source=gs(oid, f'it66 re-search: erasure_stores {item} added ({note}); grade held partial'))

# ----------------------------------------------------------------------------------------------------------------
# write
for r in orows:
    for c in C.OBL_COLS:
        r[c] = (r.get(c) or '').replace('\t', ' ').replace('\n', ' ')
cnt, ecnt = {}, {}
for r in orows:
    cnt[r['block']] = cnt.get(r['block'], 0) + 1
for r in erows:
    ecnt[r['block']] = ecnt.get(r['block'], 0) + 1
touched = {byid[x[0]]['block'] for x in ledger} | {byid[x[0]]['block'] for x in scope}
for b in brows:
    n = str(cnt.get(b['block'], 0))
    if b['obligations'] != n:
        b['obligations'] = n
C.write_tsv(f'{C.CEN}/obligations.tsv', C.OBL_COLS, orows)
C.write_tsv(f'{C.CEN}/blocks.tsv', C.BLOCKS_COLS, brows)
C.write_tsv(f'{C.CEN}/excluded.tsv', C.EXC_COLS, erows)
with open(f'{SCR}/ledger.tsv', 'w') as f:
    f.write('id\tcolumn\told\tnew\treason\n')
    for x in ledger:
        f.write('\t'.join(str(v).replace('\t', ' ') for v in x) + '\n')
with open(f'{SCR}/scope.tsv', 'w') as f:
    f.write('new_id\tfrom\tgrade\tstatement\treason\n')
    for x in scope:
        f.write('\t'.join(str(v).replace('\t', ' ') for v in x) + '\n')
print(f'retained-row column changes: {len(ledger)} on {len({x[0] for x in ledger})} rows; added rows: {len(scope)}')
