from pathlib import Path
import json
R=Path(__file__).resolve().parents[4];M=R/'.g5/Verus_verification/models/rdf_reporting';s=(M/'rdf_reporting.rs').read_text()
cs=[
('graph-scope-ignored','c.graph.is_none() || graph(g)==c.graph.unwrap()','true','theorem_graph_filter_is_request_value','source'),
('ids-ignored','c.ids.len()==0 || c.ids.contains(s)','true','theorem_outside_requested_ids_emits_nothing','source'),
('label-graph-correlation-ignored','&& graph(ls[i].graph)==graph(g)','', 'theorem_wrong_graph_membership_is_excluded','source'),
('selected-labels-widened','pub open spec fn label_selected(l:Label,c:Config)->bool {graph_selected(l.graph,c)&&id_selected(l.s,c)&&(c.labels.len()==0||c.labels.contains(l.label))}','pub open spec fn label_selected(l:Label,c:Config)->bool {graph_selected(l.graph,c)&&id_selected(l.s,c)}','theorem_label_selection_is_raw','source'),
('property-null-emitted','prop_selected(p,rs,c)&&p.value.is_some()','prop_selected(p,rs,c)','theorem_property_null_is_omitted','source'),
('empty-object-enveloped','if es.len()>0{envelope(e,pos,c)+emit_quals(es,e,pos,c)}','if true{envelope(e,pos,c)+emit_quals(es,e,pos,c)}','theorem_empty_qualifier_has_no_envelope','source'),
('inferred-only-envelope-dropped','if es.len()>0{envelope(e,pos,c)+emit_quals(es,e,pos,c)}','if es.len()>0 && exists|i:int|0<=i<es.len() && es[i].key!=t("inferred"){envelope(e,pos,c)+emit_quals(es,e,pos,c)}','theorem_inferred_only_still_has_envelope','source'),
('inferred-key-emitted','if es[0].key==t("inferred"){seq![]}else','if false{seq![]}else','lemma_inferred_quals_empty','source'),
('falsey-fallback-removed','if truth(l){l}else{Literal::Plain(s)}','l','theorem_false_and_zero_are_not_property_literals','source'),
('ftp-node-mint-removed','||starts(s,t("ftp://"))','', 'theorem_node_property_prefixes_differ','source'),
('summary-counts-quads','Report{triples:triples(qs).len()','Report{triples:qs.to_set().len()','theorem_summary_two_contexts_is_one_triple','source'),
('summary-counts-objects','nodes:subjects(qs).len()','nodes:qs.map_values(|x:Quad|x.triple.o).to_set().len()','theorem_summary_counts_subjects_not_objects','source'),
('type-counted-as-edge','pub open spec fn edge_triple(x:Triple)->bool {matches!(x.o,Term::Iri(_)) && x.p!=t("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")}','pub open spec fn edge_triple(x:Triple)->bool {matches!(x.o,Term::Iri(_))}','theorem_non_type_uri_count_rule','source'),
('json-decoded-object-dropped','if p.mode==9{p.entries}else{seq![]}','seq![]','theorem_raw_string_zero_object_is_decoded','codec'),
('json-duplicate-keeps-old','else if es[0].key==key{seq![Entry{key,value}]+es.skip(1)}','else if es[0].key==key{es}','lemma_upsert_sets_current_value','codec'),
('decimal-digit-base-wrong','n*10+(s[0] as nat-48)','n*1+(s[0] as nat-48)','theorem_two_raw_digits_determine_value','codec'),
('blank-positions-reused','let st=Term::Blank{position:pos,reifier:false};let rf=Term::Blank{position:pos,reifier:true};','let st=Term::Blank{position:0,reifier:false};let rf=Term::Blank{position:0,reifier:true};','theorem_fresh_envelope_positions','allocation relation')]
for n,f,_,_,_ in cs:assert s.count(f)==1,(n,s.count(f))
(M/'model.json').write_text(json.dumps({'name':'rdf_reporting','root':'rdf_reporting.rs','expected_verified':50,'additional_inputs':[],'product_baseline':'3eaa79cf77d3e0a879b2cced634cf2729d81499e','controls':[{'name':n,'find':f,'replace':r,'expect_fail_in':[target],'class':kind} for n,f,r,target,kind in cs]},indent=2)+'\n')
