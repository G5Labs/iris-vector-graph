"""Materialize the per-issue audit from reviewed runtime witnesses.

The selections and judgments below are human-readable review inputs, not inferred
from a binding's AGREES verdict. --write updates only the 84 selected entries.
Without --write this checks that the ledger and review are reproducible.
"""
import argparse, collections, fnmatch, hashlib, json, pathlib, re, subprocess

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
inventory = json.loads((HERE/'inventory.json').read_text())

# id | fresh evidence | defect cases | neighboring controls | observed departure
REVIEW = r'''
cyp-111|targeted-runtime|111_bad,111_type|111_control|A run-time -1 index fails and index 0 returns text; the literal -1 returns integer 3.
cyp-112|targeted-runtime|112_bad|112_control|reverse(stored list) reverses its JSON text; the literal list reverses as a list.
cyp-113|targeted-runtime|113_bad|113_control|n[k] reads property k (gotcha), not the property named by the value num (5).
cyp-114|targeted-runtime|114_bad,114_create|114_control|Five rows receive the same UUID and random number; UUID in CREATE is refused. A scalar RETURN works.
cyp-115|targeted-runtime|115_bad|115_control|Dynamic map reads return numbers, boolean and list as strings; a missing key correctly returns null.
cyp-116|targeted-runtime|116_bad|116_control|head(number) fails with an empty SQL helper message instead of a named type error; head([5]) works.
cyp-117|cypher_exprs|slice_row_-3_-1|slice_literal_-3_-1|Run-time negative bounds yield an empty slice where equivalent literal bounds select positions 2..4.
cyp-118|cypher_exprs|cond_RowVar_true,cond_Param_true,where_RowVar_true|cond_Comparison_true,cond_Literal_true|A run-time boolean condition fails SQL preparation; comparing it with true works.
cyp-119|cypher_exprs|create_node_Size,create_node_Abs|set_node_Size,create_node_ToUpper|CREATE refuses supported scalar functions that SET can evaluate; folded functions work.
cyp-120|cypher_exprs|create_rel_Call_Arith,create_rel_Param|create_rel_Lit,create_rel_matched_Param|Relationship CREATE succeeds but drops computed or parameter properties; literal properties survive.
cyp-121|cypher_exprs|coalesce_RowVar_ScalarLiteral|coalesce_NodeProp_ScalarLiteral|coalesce on a row variable returns numeric text; the typed property path returns an integer.
cyp-122|targeted-runtime|122_bad|122_control|A variable immediately before the slice separator fails parsing; a literal bound succeeds through the public API.
cyp-123|cypher_exprs|substring_row_-1_2,substring_literal_-1_2|substring_row_1_2|Negative substring offsets return characters rather than the documented argument error.
cyp-124|targeted-runtime|124_bad|124_control|Zero-length string operations return null instead of an empty string; length 1 works.
cyp-125|bolt_answers|F_unwind_param_5.3.2|F_unwind_with_5.3.2,F_unwind_param_5.4.1|The locked 5.3.2 driver fails parameter-list UNWIND; WITH indirection and driver 5.4.1 succeed.
cyp-126|targeted-runtime|126_index_bad|126_index_control|A null list index selects the first element; the out-of-range control correctly yields null.
cyp-127|cypher_exprs|simple_case_prop_str_when_num,simple_case_prop_num_when_str|simple_case_literal_str_when_num,simple_case_prop_num_when_num|Simple CASE treats stored numeric text as equal to a number; the literal mixed-type comparison does not.
cyp-128|targeted-runtime|128_bad,128_read|128_control|A list expression containing a property read raises Python TypeError without writing; a literal list writes and reads back.
cyp-129|cypher_exprs|null_list_slice_RowVar,null_list_slice_Param|null_list_slice_Literal|A null list sliced through a row or parameter path yields an empty list; the literal-null path stays null.
cyp-130|targeted-runtime|130_bad|130_control,130_create|RETURN trim keeps tabs and newlines that CREATE trim removes; trimming spaces works.
cyp-131|targeted-runtime|131_bad|131_control,131_literal|A fractional run-time range step is accepted while the equivalent literal is refused; an integer step works.
cyp-132|targeted-runtime|132_bad|132_control|A relationship SET reading its own property through toInteger is refused with a misleading cross-property error; arithmetic on its own property works.
cyp-133|sql_procs|hop_default_1,hop_named_1|hop_default_0,hop_named_0|The EDGESCAN route loses relationship properties that the normal route reads.
cyp-134|percentile|unwind:three:0.75,unwind:four:0.9|unwind:three:0,unwind:three:1|percentileDisc uses floor(p*(n-1)) instead of nearest rank; interior percentiles choose the wrong member while endpoints work.
cyp-135|cypher_clauses|A_Int1_Str1_sql_group,A_Int1_Str1_sql_countd|A_Int1_Str1_sql_distinct,A_Int1_Int2_sql_group|Grouping and count(DISTINCT) merge integer 1 with string 1 although RETURN DISTINCT separates them.
cyp-136|targeted-runtime|136_sql|136_native|The public SQL engine returns one group and the public native-enabled engine returns two for the same two stored values.
cyp-137|cypher_clauses|B_b13_sumv_plus_sumf|B_b13_bare_sumf,B_b13_sumv_plus_half|Adding property aggregates loses a fractional part through integer rounding; a bare floating sum and literal-half addition preserve it.
cyp-138|cypher_clauses|C_union_stored_int,C_dedup_stored_vs_literal_rows|C_single_stored_int,C_union_bools|UNION exposes the stored numeric marker and keeps equal stored/literal values apart; the standalone read decodes correctly.
cyp-139|cypher_clauses|D_str_2,D_bool_true,D_float_2.0,D_null|D_int_2,D_float_1.5|Pagination accepts text, boolean and whole-float counts; null is reported as missing, while fractional floats are refused.
cyp-140|cypher_clauses|E_count_union,E_count_union_all|E_count_alone,E_other_union_all|Whole-label count in a UNION fails while the count alone and neighboring union shape work.
cyp-141|cypher_clauses|F_fixed_StartNode,F_fixed_EndNode|F_matched_StartNode,F_fixed_Type|Endpoint functions fail on a relationship extracted from a path; matched-relationship endpoints and path-element type work.
cyp-142|clause_combos|C_earlier_arith,C_or_with_earlier|C_or_new_only,C_eq_earlier|OPTIONAL WHERE with arithmetic or OR reading the earlier alias is refused; adjacent predicate shapes run.
cyp-143|cypher_clauses|H_EqProps_missing|H_EqProps_present,H_OptOnly_missing|OPTIONAL WHERE drops an anchor missing the compared property instead of preserving its null optional row.
cyp-144|bolt_answers|F_slice_5.4.1,F_slice_5.3.2|F_unwind_param_5.4.1|Parameter-bound slicing returns [] on 5.4.1 and fails on 5.3.2; list UNWIND works on 5.4.1.
cyp-145|bolt_answers|G_StrLit1,G_StrParam1|G_IntLit1,G_IntParam1|A string operand matches a stored number; numeric operands use the stored-type guard.
cyp-146|cypher_clauses|I_fix1_unmatched_len,I_fix2_unmatched_len|I_fix1_matched_len,I_fix1_unmatched_nodes|An unbound optional path has its pattern length instead of null; nodes(path) correctly returns null.
cyp-147|percentile|kind:unwind:int,kind:match:int|kind:unwind:float|percentileDisc returns float for integer contributors. The neighboring continuous percentile correctly returns float.
cyp-148|percentile|p:param_null,p:param_numtext,p:lit_null|p:param_num,p:missing|Null percentile parameters raise raw TypeError, numeric text is accepted, and literal null acts as zero; numeric inputs work.
cyp-149|clause_combos|B_int_true_groups,B_list_spelled_groups,B_int_true_count_distinct|B_int_true_distinct_rows,B_int_int_groups|Mixed-kind lists merge distinct grouping keys while RETURN DISTINCT separates them.
cyp-150|targeted-runtime|150_bad|150_control|WITH * loses the relationship variable; naming n, r, b explicitly works.
cyp-151|targeted-runtime|151_bad|151_control|WITH *, expression fails parsing while the explicit projection works.
cyp-152|targeted-runtime|152_bad,152_read|152_control,152_control_read|FOREACH SET cannot resolve its loop variable and leaves f=0; a constant SET body writes f=5.
cyp-155|result_decoders|5.3.2_TX_WithCoalesce_int,5.4.1_TX_WithCoalesce_int|5.3.2_TX_Prop_int,5.4.1_TX_Prop_int|WITH coalesce returns a stored number as text on both tested drivers; the direct property read keeps its type.
cyp-156|result_decoders|5.3.2_TX_RetCase_btrue,5.4.1_TX_RetCase_int|5.4.1_TX_Prop_int|CASE returns a stored boolean as text and, on 5.4.1, a number as text; the direct property reader works.
cyp-157|targeted-runtime|157_bad|157_control|A CALL subquery importing an UNWIND variable fails with an internal SQL field error; an uncorrelated subquery succeeds.
cyp-158|targeted-runtime|158_bad|158_control|RETURN ORDER BY mixes booleans with numbers and puts text later; WITH ORDER BY produces the declared type order.
plt-015|install_lifecycle|B:x_lower_setup,D:lower16_setup,D:after_lower|D:upper16_setup|Case-only schema spelling recompiles wrong-case classes and bypasses empty-column width refusal; the original spelling refuses.
plt-026|install_lifecycle|B:y_explicit_setup,B:x_call_after_explicit|B:x_call|Explicit setup selects another schema and makes the old engine fail. Runtime is confirmed; spec 262 and ADMIN_GUIDE disagree on whether this is allowed.
plt-113|retrieval_compose|guided,guided_more|subgraph|Guided subgraphs omit edges among their returned nodes at the cap and can exceed the cap with seeds. Ordinary uncapped expansion exhibits the missing edges.
plt-114|retrieval_compose|subgraph|guided|One-hop subgraphs omit outer-node edges; capped results can include an edge to an omitted node. Two-hop expansion exposes the omitted outer edge.
plt-115|operator_reports|s9_routed_vectors:status|s9:search_g,s10_legacy_vector:status|Routed vectors search successfully but status reports zero/absent/not-ready; legacy-table vectors are counted.
plt-116|operator_reports|s4_shared_triple:verify,s5_after_heal:verify,s6_sync_again:verify|s3_put_after_sync:verify|A cross-graph duplicate triple creates permanent reported drift despite heal and sync; a single-graph case is in sync.
plt-117|operator_reports|s2_sync:caps_fresh|s15:caps_after_fresh_setup|Capabilities still say adjacency is absent after sync; another setup corrects the report.
plt-118|operator_reports|s14:viz|s14:viz|The UNLAB relationship receives endpoint label 0, which is also label A; a normal R edge has the expected label indices.
plt-119|operator_reports|s19_i53_bnative:status,s19_i53_bnative:readers|s18_ledger:status|A real restricted monitoring role gets unknown counts in text but zero counts and false readiness in API readers; privileged reads see the data.
plt-120|operator_reports|s19_i53_bnoledger:status|s18_ledger:status,s18:ledger_stats|A real role lacking ledger counter permission sees a valid head with zero commits/rejections and no error; privileged counters are nonzero.
plt-121|bolt_answers|D3_wire_s201,D3_wire_lst|D3_wire_s200|The real Bolt driver receives shortened strings/converted lists as node properties; a 200-character string survives intact.
plt-122|bolt_answers|D1_wire_collision|D1_wire_distinct|Two real node IDs with a found 31-bit hash collision arrive as the same driver node with the second value in both rows; distinct hashes keep both.
plt-123|bolt_answers|D2_wire_bra,D2_wire_rev|D2_wire_abr|Reordering RETURN columns reverses the driver's relationship endpoints relative to storage; source-first columns work.
plt-124|bolt_answers|C_iris_sql,C_driver_param|C_parse,C_read_only|The real Bolt listener calls provider/parameter failures SyntaxError; genuine parse errors and the read-only gate show the neighboring classifications.
plt-125|bolt_answers|B_wire_overflow|B_wire_9223372036854775807|An oversized integer accepted by the engine breaks the Bolt connection instead of producing FAILURE; int64 maximum arrives.
plt-126|targeted-runtime|126_bad|126_control|The real HTTP transaction route returns one node as three text columns; properties(n) returns a property map with node metadata.
plt-127|bolt_tx|D_tx_rollback,D_fail_then_rollback,D_execute_write_abort|D_tx_commit,R_empty_rollback|A real neo4j-driver rollback/aborted transaction leaves writes visible on another connection; commit and empty rollback are controls.
plt-133|install_lifecycle|A:norecord_marker_call|A:norecord_nomarker_call|An unrecorded namespace with SQL markers admits an engine; removing markers causes the expected refusal. Documentation and ontology disagree on the conjunction.
plt-134|install_lifecycle|W:e8_setup_populated,W:e8_rewidth_populated|W:e16_rewidth|Both setup modes refuse a mixed-width populated/empty layout without the documented manual-migration reply; an all-empty rewidth works.
plt-135|result_decoders|5.3.2_TX_Opt_labels,5.4.1_TX_Opt_labels|5.3.2_TX_Prop_absent|The HTTP reader exposes empty-list text for an unbound optional node; the missing scalar property correctly stays null.
plt-136|bolt_tx|H_fail_middle,H_fail_first,H_fail_last|H_all_ok,H_read_only_write|An HTTP batch with a failed statement commits successful writes and continues after failure; the read-only gate correctly prevents all writes.
srch-109|ivf_entries|cosine_ivf_search,cosine_kg_IVF|cell_cosine|Both public IVF readers rank the longer nonunit vector ahead of the aligned vector under metric cosine; cell assignment is checked separately.
srch-110|retrieval_compose|engine_fuse_building,engine_fuse_fresh,choice_building,choice_fresh|ops_fuse_fresh|Building and fresh engines select different vector legs and fusion scores over the same data. The observed trigger is engine-local state, including within one process.
srch-111|retrieval_compose|pyops_unrouted_4|engine_unrouted_4,pyops_unrouted_768|Real PyOps VectorSearch rejects a non-default-width vector on an unrouted graph; the Python engine returns no results. Deployed REST dispatch was not exercised.
srch-112|retrieval_compose|pyops_hybrid_c0|pyops_hybrid,sql_fuse|Real PyOps HybridSearch with c=0 returns the c=60 scores. Deployed REST dispatch was not exercised.
srch-113|bm25_scoring|k:sql@0,k:sql@-1|k:py@0,k:cypher@0,k:sql@1|The SQL reader returns [] for invalid k while Python/Cypher refuse it; positive k searches work.
srch-116|install_lifecycle|Q:place_ok,Q:total_conserved|QR:place_ok|A valid quarantine placement fails Cursor closed through DB-API and leaves the row quarantined. An explicitly repaired cursor-materialization control succeeds; it is not shipped behavior.
str-112|sql_procs|dj_empty_both|dj_empty_src,dj_defaults|The SQL entry returns a zero-cost path containing NUL for two empty endpoints; one empty endpoint correctly yields no path.
str-113|traversal_strategy|sp_in_p1_p3,sp_in_p3_p1|sp_out_p1_p3|The public store length method follows outgoing edges when asked for incoming direction; execute_shortest_path disagrees. No Cypher impact is claimed.
str-114|traversal_strategy|os_dirtext_OUT,os_dirtext_sideways|os_out_R_1|Invalid directions reach a real fallback and answer an undirected walk instead of refusal; canonical out uses the expected traversal.
str-115|rebuild_reads|during_sync,seed_alone_reads|quiet|During six real sync calls, concurrent readers observed the seed alone 7,182 times; 40 quiet reads saw the complete graph. No pause or provider injection forced the race.
str-117|adjacency_maint|two_hop_after_sync|two_hop_after_write|Fast/exact two-hop counts are 3/1 after sync and 1/1 after an unrelated write, confirming the unstable overcount.
tmp-103|temporal_stats|distinct_d_d1_0_299|distinct_d_nobody_0_299|One real target yields distinct count 11; an empty window yields 0, far outside the claimed small-cardinality error.
tmp-104|temporal_stats|labels|labels|Two different flat attribute sets produce the same canonical text/hash; ordinary reordered attributes correctly share their hash.
tmp-105|temporal_stats|nested|labels|Repeated identical nested values get different object-reference hashes; distinct nested maps also collide. Flat canonicalization is the neighboring case.
tmp-106|temporal_stats|ms_in_sec_whole_count,ms_in_sec_raw_window|ms_in_sec_cut_count|A millisecond-class write contaminates a seconds whole-bucket count while the raw window is empty. This requires a direct millisecond-class writer.
tmp-107|sql_procs|bf_count_1,bf_count_2,bf_rows_1,bf_rows_2|bf_rows_0|A repeated backfill still reports walked edges even though row count is unchanged; the initial run establishes actual inserted rows.
tmp-108|temporal_stats|ek_src_quiet_count,ek_src_event_count,ek_errors|ek_given_quiet_count,ek_given_event_count|An empty source returns 0 in a quiet partial window but errors when an event is met; valid-key calls have consistent results.
'''

def field(block, name):
    m = re.search(r'^'+re.escape(name)+r': (.*?)(?=\n\n|\Z)', block, re.M|re.S)
    return m.group(1) if m else ''

def evidence(name):
    raw = json.loads((HERE/'evidence'/f'{name}.json').read_text())
    if name == 'targeted-runtime': return raw, raw['cases']
    assert raw['exit_code'] == 0 and raw['receipt']['verdict'] == 'AGREES', name
    r = raw['receipt']
    v = r.get('observed',r.get('cells',r))
    if isinstance(v,list): v = {x['name']:x for x in v}
    return raw,v

def select(v, patterns):
    result = {}
    for pattern in patterns.split(','):
        keys = [k for k in v if fnmatch.fnmatchcase(k,pattern)]
        assert keys, pattern
        result.update({k:v[k] for k in keys})
    return result

def build():
    byid = {e['id']:e for e in inventory['issues']}
    rows = []
    for line in REVIEW.strip().splitlines():
        short, suite, bad, controls, assessment = line.split('|')
        id = 'bug-'+short
        old = byid[id]
        raw,v = evidence(suite)
        row = dict(id=id,title=old['title'],disposition='retain',severity=old['severity'],
                   reproduction='partial' if short in ('srch-111','srch-112') else 'e2e',
                   evidence='evidence/'+suite+'.json',
                   defect_cases=select(v,bad),control_cases=select(v,controls),
                   assessment=assessment,expected=field(old['block'],'Expected'),
                   severity_basis=field(old['block'],'Consequence'),
                   limits=('Real PyOps component; HTTP deployment, dispatch, authentication and response are untested.'
                           if short in ('srch-111','srch-112') else
                           'Only the named public API, SQL entry, transport or documented setup operation on IRIS Community 2026.1 and the recorded drivers. This does not certify every route or provider version.'))
        if short in ('plt-026','plt-133'):
            row['intent_qualification']='Runtime reproduced; source documents conflict. Retained as a Low contract/documentation discrepancy, not an owner-approved product-policy decision.'
        if short == 'plt-126':
            row['intent_qualification']='Neo4j HTTP compatibility discrepancy; the narrower current access.surfaces ontology does not itself settle node response shape.'
        if short == 'cyp-125':
            row['severity_basis']='Medium: a real public read pattern fails in the product-lock driver environment. Driver 5.4.1 is a passing control. UNWIND CREATE uses another route and is not shown broken; future driver support policy remains open.'
        if short == 'srch-110':
            row['limits']='Building versus fresh engine instances reproduced within one process. This establishes engine-instance dependence; restart/cross-process impact follows the same cache mechanism but was not independently replayed in this audit.'
        rows.append(row)
    assert {x['id'] for x in rows} == set(byid) and len(rows)==84
    # Replay identity and source provenance. No modified shipped code was tested.
    mismatches=[]; checked={}
    for p in (HERE/'evidence').glob('*.json'):
        d=json.loads(p.read_text()); r=d.get('receipt',{})
        for f,h in r.get('inputs',{}).items():
            if not isinstance(h,str) or len(h)!=64: continue
            src=ROOT/f
            if src.is_file():
                actual=hashlib.sha256(src.read_bytes()).hexdigest();checked[f]=h
                if actual!=h:mismatches.append(f)
    assert not mismatches, mismatches
    return dict(scope='84 entries added/reinstated between the frozen 192- and 276-entry registers; not 84 independent root causes.',
                product='3eaa79cf77d3e0a879b2cced634cf2729d81499e',
                before=inventory['before'],after=inventory['after'],source=inventory['source'],
                totals={'reviewed':84,'retained':len(rows),'removed':0,
                        'e2e':sum(r['reproduction']=='e2e' for r in rows),'partial':sum(r['reproduction']=='partial' for r in rows),
                        'severity':dict(collections.Counter(r['severity'] for r in rows))},
                unchanged_input_files_checked=len(checked),issues=rows)

def render(d):
    s = '''# Reproduction audit of the 84 added IRIS findings

All 84 added or reinstated entries have a fresh applicable runtime witness: **82 E2E and 2 partial**. **None was removed** for lack of reproduction. Severity: **3 High, 40 Medium, 41 Low; no Critical**. The older 192 entries were outside this review. These are issue entries, with overlapping causes and three reinstated IDs, not 84 independent bugs.

The audit ran all 18 relevant native binding suites and an independent public-entry probe on unchanged product `3eaa79cf77d3e0a879b2cced634cf2729d81499e`, IRIS Community 2026.1, in the isolated `ivg-cont-20261117-iris` container. The two parameter-driver environments were 5.3.2 and 5.4.1; TCP Bolt used the real neo4j driver. HTTP witnesses used the real FastAPI application and database in-process; they do not test a reverse proxy or network deployment. No product bug was repaired. Source hashes are checked against the fresh receipts.

E2E means the stated public operation reached the real database/provider and its output or persistent effect was observed; it does not mean every interface was exercised. The two partial reports call real PyOps code but do not traverse the deployed ObjectScript REST routes. A binding's `AGREES` verdict means its as-built prediction matches the product. The defect judgment below separately compares the observed result with the stated contract and a neighboring control. Mutation controls are not product reproductions. Quarantine's repaired-cursor control is identified as such.

The strongest retained reports are silent relationship-property loss during CREATE (`bug-cyp-120`), incomplete guided-subgraph output (`bug-plt-113`) and writes surviving an acknowledged Bolt rollback (`bug-plt-127`). The concurrency report also reproduced without forced scheduling: 7,182 reads saw only the seed during six sync calls; all 40 quiet controls saw the complete graph.

Two setup entries (`bug-plt-026`, `bug-plt-133`) reproduce an explicit disagreement between sources, so their intended policy remains a human decision. The HTTP node-shape entry is a compatibility discrepancy, not proof that its current narrower ontology promises that shape. `bug-cyp-125` is now consistently described as reproduced on the lockfile's 5.3.2 driver and passing on 5.4.1; its old untested-5.4/bulk-write claims were removed. `bug-srch-110` is narrowed to building versus fresh engine instances: the replay demonstrates that distinction within one process, without claiming a separately tested restart.

## Replay

The committed [runner](replay_bindings.py) exports the frozen foundation `1a9facfb` into a separate VM audit directory and runs the binding scripts with the existing isolated fixture venv. Run it on the experiment VM with `python3 replay_bindings.py`; then run [targeted_runtime.py](targeted_runtime.py) with that fixture's venv. These scripts are fixture-specific and deliberately do not provision or touch a production database. Preserve the remote `~/experiments/iris-issue-reproduction-20261117/evidence` directory here. Re-run `python3 .g5/Verus_verification/audits/reproduction-20261117/adjudicate.py` from the checkout to check the reviewed case references, source hashes and generated ledger. `--write` is only for applying the reviewed register reconciliation.

The [machine-readable ledger](adjudication.json) includes exact defect/control case IDs and their observed values, the expected contract, severity basis and limits for every issue. [Inventory](inventory.json) and [pre-edit register](before/bugs_issues.md) preserve the starting entries. All current entries remain in the [authoritative issue register](../../bugs_issues.md).

Validation: the audit's case/source checks and experiment-page generation/link checks pass. The shared findings-format checker still reports the same 277 pre-existing findings: 276 descriptions precede their Run line and one ontology backlink is absent. This audit introduces none of those errors and preserves the prior description edits. See [validation](validation.json).

## Per-issue disposition

| Issue | Severity | Runtime scope | Observed departure and control |
|---|---|---|---|
'''
    for r in d['issues']:
        s += f"| [{r['id']}](../../bugs_issues.md#{r['id']}) | {r['severity']} | [{'E2E' if r['reproduction']=='e2e' else 'Partial'}]({r['evidence']}) | {r['assessment']} |\n"
    return s

def update_register(d):
    p=ROOT/'.g5/Verus_verification/bugs_issues.md';t=p.read_text()
    old_by_id={e['id']:e for e in inventory['issues']}
    for r in d['issues']:
        old=old_by_id[r['id']]['block']
        assert old in t, 'Starting entry changed: '+r['id']
        label='E2E reproduced' if r['reproduction']=='e2e' else 'Partially reproduced'
        cases=', '.join('`'+k+'`' for k in r['defect_cases'])
        rep=f"**{label}** in the independent 2026-11-17 audit on unchanged product `3eaa79cf`, real IRIS 2026.1. [Fresh runtime evidence](audits/reproduction-20261117/{r['evidence']}), cases {cases}. {r['assessment']} [Exact inputs, controls, severity and limits](audits/reproduction-20261117/adjudication.json)."
        new=re.sub(r'^Reproduced by: .*?(?=\n\n|\Z)',lambda _: 'Reproduced by: '+rep,old,count=1,flags=re.M|re.S)
        if r.get('intent_qualification'):
            new+='Audit qualification: '+r['intent_qualification']+'\n\n'
        if r['id']=='bug-cyp-125':
            new=re.sub(r'^Found by: .*?(?=\n\n)', 'Found by: the first `cypher_exprs` binding run and its follow-up. The driver comparison and current formal account are [bolt_answers](models/bolt_answers/NOTES.md), `theorem_unwind_param_depends_on_driver` (provider premise P-DRV-JT). This audit independently replayed both driver environments.',new,flags=re.M|re.S)
            new=re.sub(r'^Description: .*?(?=\n\n)', 'Description: The lockfile\'s IRIS driver 5.3.2 cannot expand a list parameter in a read query; the same query works with 5.4.1. The supported-driver policy remains open, but the locked-environment failure is reproduced.',new,flags=re.M|re.S)
            new=re.sub(r'^Observed: .*?(?=\n\n)', 'Observed: The fresh two-driver replay confirms that 5.3.2 fails parameter-list UNWIND and 5.4.1 binds it correctly. The product lockfile selects 5.3.2. This is a provider-dependent, reachable read-query failure, not an untested conjecture about 5.4.x.',new,flags=re.M|re.S)
            new=re.sub(r'^Consequence: .*?(?=\n\n)', 'Consequence: A public parameter-list read fails in the locked environment. Medium. WITH indirection or driver 5.4.1 avoids this read failure. UNWIND CREATE follows a different route and was observed to write on both drivers; this entry does not claim that bulk writes fail.',new,flags=re.M|re.S)
        if r['id']=='bug-srch-110':
            new=new.replace("The engine's fusion reads a cosine IVF index only in the process that built it, so the same call ranks differently elsewhere", "Fusion chooses a different vector leg on the engine that built a cosine IVF index and on a fresh engine")
            new=re.sub(r'^Description: .*?(?=\n\n)', 'Description: Fusion retains index-selection state on the engine instance that built the IVF index. A fresh engine over the same data selects a different vector leg and can change the fused ranking, even within one process.',new,flags=re.M|re.S)
            new=re.sub(r'^Consequence: .*?(?=\n\n)', 'Consequence: Replacing the engine instance can silently change fusion results over the same data when stored vectors are not unit length. Medium: the replay establishes engine-instance dependence within one process. A separate restart or cross-process test was not run in this audit.',new,flags=re.M|re.S)
        t=t.replace(old,new,1)
    intro='Each entry explains a recorded problem, its impact and the evidence. Findings that still need confirmation are marked in their entries.'
    t=t.replace(intro,intro+' The [84-entry reproduction audit](audits/reproduction-20261117/REVIEW.md) records the evidence and severity of the additions from the latest loop: 82 E2E, 2 partial, none without a runtime witness.',1)
    p.write_text(t)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--write',action='store_true');args=a.parse_args()
    d=build()
    artifacts={'adjudication.json':json.dumps(d,indent=2,ensure_ascii=False)+'\n','REVIEW.md':render(d)}
    for name,body in artifacts.items():
        p=HERE/name
        if args.write:p.write_text(body)
        else:assert p.read_text()==body,'Stale generated audit: '+str(p)
    if args.write:update_register(d)
    print(json.dumps(d['totals'],indent=2))
