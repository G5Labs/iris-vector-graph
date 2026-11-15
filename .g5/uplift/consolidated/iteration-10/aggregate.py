import datetime,hashlib,json,re
from pathlib import Path
R=Path.cwd();O=R/'.g5/uplift/consolidated/iteration-10';V=R/'.g5/Verus_verification'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
latest={}
for fam in ['weighted_cost','ppr_walk']:
 m=json.loads((V/'models'/fam/'model.json').read_text());rs=V/'results'/fam;latest[fam]={}
 for key,pattern in [('proof','*-prove/receipt.json'),('binding','*-binding/receipt.json')]+[(c['name'],'*-control-'+c['name']+'/receipt.json') for c in m['controls']]:
  p=sorted(rs.glob(pattern))[-1];d=json.loads(p.read_text());stale=[k for k,h in d['inputs'].items() if sha(R/k)!=h];assert not stale,(fam,key,stale)
  expected='PASS' if key=='proof' else 'AGREES' if key=='binding' else 'EXPECTED_FAIL';assert d['verdict']==expected,(fam,key,d['verdict'])
  latest[fam][key]=dict(path=str(p.relative_to(R)),sha256=sha(p),verdict=d['verdict'],verified=d.get('observed',{}).get('verified'),comparisons=d.get('comparisons',d.get('cases')),inputs_match=True,input_count=len(d['inputs']))
before=json.loads((O/'before-reach/bindings.json').read_text());after=json.loads((O/'after-reach/bindings.json').read_text())
# Census outputs retain full reverse bindings; measure membership, not link count.
def members(v):
 if isinstance(v,dict):return set(v)
 return set(x.get('member',x.get('key',str(x))) for x in v)
bs=json.loads((O/'before-reach/summary.json').read_text());a=json.loads((O/'after-reach/summary.json').read_text());assert a['denominator']==bs['denominator']==4130
print('binding format',type(before).__name__,list(before)[:1])
proofs={}
for fam in latest:
 s=(V/'models'/fam/(fam+'.rs')).read_text();proofs[fam]=dict(proof_declarations=len(re.findall(r'\bproof fn\b',s)),named_theorems=len(re.findall(r'\bproof fn theorem_',s)))
cost=json.loads((O/'cost-builder-validation.json').read_text());ppr=json.loads((O/'ppr-costs.json').read_text())
validation=dict(product_pin='3eaa79cf77d3e0a879b2cced634cf2729d81499e',input='e56c8592b040abb08eafefed65ae17e2f56bd673',latest=latest,new_units=dict(weighted_cost=43,ppr_walk=103,total=146,proof_declarations=108,named_theorems=40,helpers=68,spec_termination=21,nonlinear_arithmetic_subqueries=17,imported_rechecked=45,total_verifier_units_including_import=191),controls=dict(total=32,weighted_cost=8,ppr_walk=24,named_ordinary_failures=32,ppr_whole_producer_cap_mutant_collateral_resource_limit=True,scope='All final named isolated obligations fail ordinarily. Whole-mutant collateral resource errors do not earn credit.'),native=dict(cost_cases=15,ppr_tie_cases=6,ppr_cap_cases=4,prior_iteration_reverse_weight_pairs_reused=5,scope='Serial identity-guarded task-owned Community runtime; pinned source/export correspondence reuses setup5, not native executable-body verification. Direct fallback is not native provider-outage dispatch.'),unit_tests=dict(ppr=87,vector_next_survey=23,scope='Vector survey preparation has no iteration10 formal/reach credit.'),reach=dict(before=188,after=197,denominator=4130,new=9,lost=0,direct_body_verified=0),role_audit=dict(active_rows=9,observations=14,new_rows=23),registers=dict(bugs=432,simplifications=55,questions=146,new_bugs=2,new_questions=1,questions_resolved=0,owner_decisions=0,repairs_or_simplifications_accepted=0),freshness_fixtures=11,consolidated_gate=dict(verdict='PASS',ontology_blocks=401,role_links=282,writing_issues=0,writing_warnings=0,log=str((O/'consolidated-gate.log').relative_to(R))),cost=dict(start=json.loads((O/'inputs.json').read_text())['time'],recorded_now=datetime.datetime.now(datetime.timezone.utc).isoformat(),weighted_builder_elapsed_s=cost['elapsed_builder_s'],weighted_verifier_attempt_sum_s_timestamp_resolution=cost['verifier_wall_s_sum_timestamp_resolution'],ppr_ledger='ppr-costs.json',review_ledgers=['cost-review-validation.json','ppr-review-validation.json'],tokens_cache_currency_solver_only_cpu='unavailable',independent_grader='not run'),convergence='unsupported; route/query validation workflow and positive fractional weighted arithmetic remain material and tractable; no fixed time/round/percentage budget')
(O/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
print(json.dumps(dict(latest_fresh=sum(len(x) for x in latest.values()),units=validation['new_units'],proofs=proofs)))
