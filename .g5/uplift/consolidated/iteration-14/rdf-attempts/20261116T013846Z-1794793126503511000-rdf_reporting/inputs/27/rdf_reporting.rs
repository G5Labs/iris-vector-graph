use vstd::prelude::*;
use vstd::seq_lib::*;
mod lexical;
mod json;
use lexical::*;
use json::*;
verus! {
pub struct Label {pub graph:Option<Text>,pub s:Text,pub label:Text}
pub struct Property {pub graph:Option<Text>,pub s:Text,pub key:Text,pub value:Option<Text>}
pub struct Edge {pub graph:Option<Text>,pub s:Text,pub p:Text,pub o:Text,pub qualifiers:Option<Text>}
pub struct Rows {pub labels:Seq<Label>,pub props:Seq<Property>,pub edges:Seq<Edge>}
pub struct Config {pub graph:Option<Text>,pub ids:Seq<Text>,pub labels:Seq<Text>,pub base:Text}
pub enum Term {Iri(Text),Blank{position:nat,reifier:bool},Literal(Literal)}
pub struct Triple {pub s:Term,pub p:Text,pub o:Term}
pub struct Quad {pub graph:Text,pub triple:Triple}
pub struct Report {pub triples:nat,pub nodes:nat,pub edges:nat}
pub open spec fn graph(g:Option<Text>)->Text {g.unwrap_or(Seq::empty())}
pub open spec fn graph_selected(g:Option<Text>,c:Config)->bool {c.graph.is_none() || graph(g)==c.graph.unwrap()}
pub open spec fn id_selected(s:Text,c:Config)->bool {c.ids.len()==0 || c.ids.contains(s)}
pub open spec fn member(ls:Seq<Label>,s:Text,g:Option<Text>,c:Config)->bool {
 c.labels.len()==0 || exists|i:int|0<=i<ls.len() && ls[i].s==s && graph(ls[i].graph)==graph(g) && c.labels.contains(ls[i].label)
}
pub open spec fn label_selected(l:Label,c:Config)->bool {graph_selected(l.graph,c)&&id_selected(l.s,c)&&(c.labels.len()==0||c.labels.contains(l.label))}
pub open spec fn prop_selected(p:Property,rs:Rows,c:Config)->bool {graph_selected(p.graph,c)&&id_selected(p.s,c)&&member(rs.labels,p.s,p.graph,c)}
pub open spec fn edge_selected(e:Edge,rs:Rows,c:Config)->bool {graph_selected(e.graph,c)&&id_selected(e.s,c)&&member(rs.labels,e.s,e.graph,c)}
pub open spec fn q(g:Option<Text>,s:Term,p:Text,o:Term)->Quad {Quad{graph:graph(g),triple:Triple{s,p,o}}}
pub open spec fn uri(x:Text,c:Config)->Term {Term::Iri(mint(x,c.base))}
pub open spec fn emit_label(l:Label,c:Config)->Seq<Quad> {if label_selected(l,c){seq![q(l.graph,uri(l.s,c),t("rdf:type"),uri(l.label,c))]}else{seq![]}}
pub open spec fn emit_prop(p:Property,rs:Rows,c:Config)->Seq<Quad> {if prop_selected(p,rs,c)&&p.value.is_some(){seq![q(p.graph,uri(p.s,c),property_predicate(p.key,c.base),Term::Literal(literal(p.value.unwrap())))]}else{seq![]}}
pub open spec fn emit_quals(es:Seq<Entry>,e:Edge,pos:nat,c:Config)->Seq<Quad> decreases es.len() {
 if es.len()==0{seq![]}else{(if es[0].key==t("inferred"){seq![]}else{seq![q(e.graph,Term::Blank{position:pos,reifier:true},t("urn:ivg:qualifier/")+es[0].key,Term::Literal(qualifier_literal(es[0].value)))]})+emit_quals(es.skip(1),e,pos,c)}
}
pub open spec fn envelope(e:Edge,pos:nat,c:Config)->Seq<Quad> {
 let st=Term::Blank{position:pos,reifier:false};let rf=Term::Blank{position:pos,reifier:true};
 seq![q(e.graph,st,t("rdf:subject"),uri(e.s,c)),q(e.graph,st,t("rdf:predicate"),uri(e.p,c)),q(e.graph,st,t("rdf:object"),uri(e.o,c)),q(e.graph,rf,t("rdf:reifies"),st)]
}
pub open spec fn emit_edge(e:Edge,rs:Rows,pos:nat,c:Config)->Seq<Quad> {
 if !edge_selected(e,rs,c){seq![]}else{let es=decode(e.qualifiers);
 seq![q(e.graph,uri(e.s,c),mint(e.p,c.base),uri(e.o,c))]+(if es.len()>0{envelope(e,pos,c)+emit_quals(es,e,pos,c)}else{seq![]})}
}
pub open spec fn emit_labels(ls:Seq<Label>,c:Config)->Seq<Quad> decreases ls.len() {if ls.len()==0{seq![]}else{emit_label(ls[0],c)+emit_labels(ls.skip(1),c)}}
pub open spec fn emit_props(ps:Seq<Property>,rs:Rows,c:Config)->Seq<Quad> decreases ps.len() {if ps.len()==0{seq![]}else{emit_prop(ps[0],rs,c)+emit_props(ps.skip(1),rs,c)}}
pub open spec fn emit_edges(es:Seq<Edge>,rs:Rows,offset:nat,c:Config)->Seq<Quad> decreases es.len() {if es.len()==0{seq![]}else{emit_edge(es[0],rs,offset,c)+emit_edges(es.skip(1),rs,offset+1,c)}}
pub open spec fn generated(rs:Rows,c:Config)->Seq<Quad> {emit_labels(rs.labels,c)+emit_props(rs.props,rs,c)+emit_edges(rs.edges,rs,0,c)}
pub open spec fn quadset(rs:Rows,c:Config)->Set<Quad> {generated(rs,c).to_set()}
pub open spec fn triples(qs:Seq<Quad>)->Set<Triple> {qs.map_values(|q:Quad|q.triple).to_set()}
pub open spec fn subjects(qs:Seq<Quad>)->Set<Term> {qs.map_values(|q:Quad|q.triple.s).to_set()}
pub open spec fn edge_triple(x:Triple)->bool {matches!(x.o,Term::Iri(_)) && x.p!=t("rdf:type")}
pub open spec fn reported(rs:Rows,c:Config)->Report {
 let qs=generated(rs,c);Report{triples:triples(qs).len(),nodes:subjects(qs).len(),edges:qs.map_values(|q:Quad|q.triple).filter(|x:Triple|edge_triple(x)).to_set().len()}}
pub open spec fn origin(x:Quad,rs:Rows,c:Config)->bool {
 (exists|i:int|0<=i<rs.labels.len() && emit_label(rs.labels[i],c).contains(x)) ||
 (exists|i:int|0<=i<rs.props.len() && emit_prop(rs.props[i],rs,c).contains(x)) ||
 (exists|i:int|0<=i<rs.edges.len() && emit_edge(rs.edges[i],rs,i as nat,c).contains(x))
}
pub proof fn theorem_label_selection_is_raw(l:Label,c:Config)
 ensures emit_label(l,c).len()>0 <==> graph_selected(l.graph,c)&&id_selected(l.s,c)&&(c.labels.len()==0||c.labels.contains(l.label))
{}
pub proof fn theorem_empty_filters_are_unfiltered(s:Text,ls:Seq<Label>,g:Option<Text>,base:Text)
 ensures id_selected(s,Config{graph:None,ids:seq![],labels:seq![],base}),member(ls,s,g,Config{graph:None,ids:seq![],labels:seq![],base})
{}
pub proof fn theorem_wrong_graph_membership_is_excluded(ls:Seq<Label>,s:Text,g:Option<Text>,c:Config)
 requires c.labels.len()>0,forall|i:int|0<=i<ls.len() && ls[i].s==s ==> graph(ls[i].graph)!=graph(g)
 ensures !member(ls,s,g,c)
{}
pub proof fn theorem_source_not_target_selects(e:Edge,rs:Rows,c:Config)
 requires !id_selected(e.s,c)
 ensures emit_edge(e,rs,0,c).len()==0
{}
pub proof fn theorem_property_null_is_omitted(p:Property,rs:Rows,c:Config)
 requires p.value.is_none()
 ensures emit_prop(p,rs,c).len()==0
{}
pub proof fn theorem_fresh_envelope_positions(e:Edge,c:Config,i:nat,j:nat)
 requires i!=j
 ensures !envelope(e,j,c).contains(envelope(e,i,c)[0]),envelope(e,i,c)[0].triple.s!=envelope(e,j,c)[0].triple.s
{}
pub proof fn theorem_envelope_has_two_derived_blank_subjects(e:Edge,c:Config,i:nat)
 ensures subjects(envelope(e,i,c))==set![Term::Blank{position:i,reifier:false},Term::Blank{position:i,reifier:true}]
{assert(envelope(e,i,c).map_values(|q:Quad|q.triple.s) =~= seq![Term::Blank{position:i,reifier:false},Term::Blank{position:i,reifier:false},Term::Blank{position:i,reifier:false},Term::Blank{position:i,reifier:true}]);}
pub proof fn theorem_original_object_decides_envelope(e:Edge,rs:Rows,c:Config,pos:nat)
 requires edge_selected(e,rs,c),decode(e.qualifiers).len()>0
 ensures emit_edge(e,rs,pos,c).contains(envelope(e,pos,c)[0])
{}
pub proof fn theorem_non_type_uri_count_rule(x:Triple)
 ensures edge_triple(x)==(matches!(x.o,Term::Iri(_)) && x.p!=t("rdf:type"))
{}
}
