from pathlib import Path
import json
p=Path('.g5/Verus_verification/models/weighted_fraction/weighted_fraction.rs');s=p.read_text();controls=[]
def add(n,w,f,r,t):
    assert s.count(f)==1,(n,s.count(f))
    controls.append(dict(name=n,why=w,find=f,replace=r,expect_fail_in=[t]))
add('default-unit-not-scaled','None/nonpositive raw scalar is effective one, so encoded value must be D.','*factor(c,a)}else{denominator(c)}','*factor(c,a)}else{1nat}','theorem_scalar_and_cap_decode')
add('positive-numerator-not-scaled','Positive raw numerator needs every other denominator factor.','(c.raw[a].unwrap().num as nat)*factor(c,a)','(c.raw[a].unwrap().num as nat)','theorem_scalar_and_cap_decode')
add('zero-raw-not-defaulted','Zero raw scalar is effective one, not zero.','c.raw[a].unwrap().num>0{(c.raw[a].unwrap().num as nat)','c.raw[a].unwrap().num>=0{(c.raw[a].unwrap().num as nat)','theorem_scalar_and_cap_decode')
add('cap-omits-common-factor','Cap denominator participates in the derived common grid.','(c.cap.num as nat)*omitted(denominations(c),c.arcs.len())','(c.cap.num as nat)','theorem_cap_decode')
add('json-removes-stale-entry','Actual JSON adds improved entry while retaining its stale predecessor.','queue:s.queue.insert((n,a.4,h)),dist:s.dist.insert(k,n)','queue:(if s.dist.contains_key(k){s.queue.remove((s.dist[k],a.4,h))}else{s.queue}).insert((n,a.4,h)),dist:s.dist.insert(k,n)','theorem_json_relax_commutes')
add('json-parent-weight-one','The real parent records actual effective fractional weight for backtrack.','((e.1,e.2),a,weight(c,a))),..s','((e.1,e.2),a,1real)),..s','theorem_json_relax_commutes')
add('cost-retains-old-queue','Actual Cost removes old queue entry on a strict distance decrease.','let q=if z.dist.contains_key(v){z.queue.remove((z.dist[v],v))}else{z.queue};\n        Side','let q=z.queue;\n        Side','theorem_cost_decrease_commutes')
add('cost-best-hop-loses-half','Historical BestHop includes both path halves.','best_hops:side(t,false).hop[v]+side(t,true).hop[v]','best_hops:side(t,false).hop[v]','theorem_cost_relax_commutes')
add('cost-both-backward-order','Backward both scan reverses its primary tag.','if b{(1-f) as nat}else{f}','if b{f}else{f}','lemma_cost_neighbor_sequence')
add('cost-frontsum-one-early','Frontier stop compares the exact real sum against Best.','if s.best.is_some() && f.0+r.0>=s.best.unwrap(){CEvent::Halt','if s.best.is_some() && f.0+r.0+1real>=s.best.unwrap(){CEvent::Halt','theorem_cost_step_commutes')
add('cost-hop-fallback-removed','Over-bound historical cheapest path calls actual raw JSON with unchanged config.','else if c.bound>0 && s.best_hops>c.bound{janswer(c)}','else if false{janswer(c)}','theorem_cost_finish_commutes')
add('json-reader-total-zero','Final JSON reader exposes the actual accepted real cost.','Path{arcs:p.arcs,costs:p.costs,total:e.0}','Path{arcs:p.arcs,costs:p.costs,total:0real}','theorem_json_reader_raw_fields')
add('self-zero-one','The self branch returns zero even for a negative cap.','Some(Path{arcs:seq![],costs:seq![],total:0real})','Some(Path{arcs:seq![],costs:seq![],total:1real})','theorem_raw_signed_rational_json')
m=p.with_name('model.json');j=json.loads(m.read_text());j['expected_verified']=181;j['controls']=controls;m.write_text(json.dumps(j,indent=2)+'\n')
