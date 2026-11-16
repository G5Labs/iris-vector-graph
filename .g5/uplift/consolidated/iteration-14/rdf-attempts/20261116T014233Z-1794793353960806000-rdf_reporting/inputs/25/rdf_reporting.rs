use vstd::prelude::*;
use vstd::seq_lib::*;
mod lexical {
use vstd::prelude::*;
verus! {
pub type Text=Seq<char>;
pub open spec fn t(s:&str)->Text {s@}
pub open spec fn starts(s:Text,p:Text)->bool {s.len()>=p.len() && s.take(p.len() as int)==p}
pub open spec fn ends(s:Text,p:Text)->bool {s.len()>=p.len() && s.skip((s.len()-p.len()) as int)==p}
pub open spec fn lower(s:Text)->Text {s.map_values(|c:char|if 'A'<=c<='Z'{((c as u32)+32) as char}else{c})}
pub open spec fn digit(c:char)->bool {'0'<=c<='9'}
pub open spec fn digits(s:Text,n:nat)->Option<nat> decreases s.len() {
 if s.len()==0 {Some(n)}else if digit(s[0]) {digits(s.skip(1),n*10+(s[0] as nat-48) as nat)}else{None}}
pub open spec fn canonical_integer(s:Text)->Option<int> {
 let neg=s.len()>0 && s[0]=='-';let ds=if neg{s.skip(1)}else{s};
 if ds.len()==0 || (ds.len()>1 && ds[0]=='0') || (neg && ds==t("0")){None}
 else{match digits(ds,0){Some(n)=>Some(if neg{-(n as int)}else{n as int}),None=>None}}
}
pub struct Decimal {pub n:int,pub d:nat,pub spelling:Text}
pub open spec fn dyadic(s:Text)->Option<Decimal> {
 let (suffix,den,part)=if ends(s,t(".25")){(t(".25"),4nat,1int)}else if ends(s,t(".75")){(t(".75"),4nat,3int)}else if ends(s,t(".5")){(t(".5"),2nat,1int)}else{(t(".0"),1nat,0int)};
 if !ends(s,suffix){None}else{
 let prefix=s.take((s.len()-suffix.len()) as int);
 match canonical_integer(prefix){Some(n)=>if -1000<=n<=1000 {Some(Decimal{n:(if den==4{n*4}else if den==2{n*2}else{n})+(if n<0{-part}else{part}),d:den,spelling:s})}else{None},None=>None}}
}
pub enum Literal {Integer{value:int,spelling:Text},Decimal(Decimal),Boolean(bool),Plain(Text)}
pub open spec fn literal(s:Text)->Literal {
 match canonical_integer(s) {Some(n)=>Literal::Integer{value:n,spelling:s},None=>{
 match dyadic(s){Some(d)=>Literal::Decimal(d),None=>{
 if s==t("007"){Literal::Decimal(Decimal{n:7,d:1,spelling:t("7.0")})}
 else if lower(s)==t("true"){Literal::Boolean(true)}else if lower(s)==t("false"){Literal::Boolean(false)}else{Literal::Plain(s)}
 }}}}
}
pub open spec fn truth(l:Literal)->bool {match l {Literal::Integer{value,..}=>value!=0,Literal::Decimal(d)=>d.n!=0,Literal::Boolean(b)=>b,Literal::Plain(s)=>s.len()>0}}
pub open spec fn qualifier_literal(s:Text)->Literal {let l=literal(s);if truth(l){l}else{Literal::Plain(s)}}
pub open spec fn plain(s:Text)->bool {s.len()==0 || (s.len()>0 && (('a'<=s[0]<='z') || ('A'<=s[0]<='Z')) && lower(s)!=t("nan") && lower(s)!=t("inf") && lower(s)!=t("infinity") && forall|i:int|0<=i<s.len() ==> (('a'<=s[i]<='z') || ('A'<=s[i]<='Z') || digit(s[i]) || s[i]=='_' || s[i]=='-' || s[i]=='/' || s[i]==':' || s[i]=='.'))}
pub open spec fn admitted(s:Text)->bool {canonical_integer(s).is_some() || dyadic(s).is_some() || s==t("007") || plain(s)}
pub open spec fn mint(s:Text,base:Text)->Text {
 if starts(s,t("http://"))||starts(s,t("https://"))||starts(s,t("urn:"))||starts(s,t("ftp://")){s}else{base+s}}
pub open spec fn property_predicate(s:Text,base:Text)->Text {
 if starts(s,t("http://"))||starts(s,t("https://"))||starts(s,t("urn:")){mint(s,base)}else{t("urn:ivg:prop/")+s}}
pub proof fn theorem_canonical_integer_is_derived(s:Text,n:int)
 requires canonical_integer(s)==Some(n)
 ensures literal(s)==(Literal::Integer{value:n,spelling:s})
{}
pub proof fn theorem_dyadic_is_derived(s:Text,d:Decimal)
 requires canonical_integer(s).is_none(),dyadic(s)==Some(d)
 ensures literal(s)==Literal::Decimal(d),d.d==1||d.d==2||d.d==4,-4003<=d.n<=4003,d.spelling==s
{}
pub proof fn theorem_falsey_qualifier_fallback(s:Text)
 ensures !truth(literal(s)) ==> qualifier_literal(s)==Literal::Plain(s),truth(literal(s)) ==> qualifier_literal(s)==literal(s)
{}
pub proof fn theorem_node_property_prefixes_differ(s:Text,base:Text)
 requires starts(s,t("ftp://")),!starts(s,t("http://")),!starts(s,t("https://")),!starts(s,t("urn:"))
 ensures mint(s,base)==s,property_predicate(s,base)==t("urn:ivg:prop/")+s
{}
pub proof fn theorem_false_and_zero_are_not_property_literals()
 ensures literal(t("false"))==Literal::Boolean(false),qualifier_literal(t("false"))==Literal::Plain(t("false")),
 literal(t("0"))==(Literal::Integer{value:0,spelling:t("0")}),qualifier_literal(t("0"))==Literal::Plain(t("0"))
{reveal_strlit("false");reveal_strlit("true");reveal_strlit("0");reveal_strlit("007");reveal_strlit(".25");reveal_strlit(".75");reveal_strlit(".5");reveal_strlit(".0");assert(lower(t("false")) =~= t("false"));reveal_with_fuel(digits,2);}
}

}
mod json {
use vstd::prelude::*;
use vstd::seq_lib::*;
use super::lexical::*;
verus! {
pub struct Entry {pub key:Text,pub value:Text}
pub open spec fn key_fn()->spec_fn(Entry)->Text {|e:Entry|e.key}
pub open spec fn upsert(es:Seq<Entry>,key:Text,value:Text)->Seq<Entry> decreases es.len() {
 if es.len()==0{seq![Entry{key,value}]}else if es[0].key==key{seq![Entry{key,value}]+es.skip(1)}else{seq![es[0]]+upsert(es.skip(1),key,value)}}
pub open spec fn unique(es:Seq<Entry>)->bool {forall|i:int,j:int|0<=i<j<es.len() ==> es[i].key!=es[j].key}
pub struct Parser {pub mode:nat,pub key:Text,pub value:Text,pub entries:Seq<Entry>}
pub open spec fn initial()->Parser {Parser{mode:0,key:Seq::empty(),value:Seq::empty(),entries:Seq::empty()}}
pub open spec fn bare(s:Text)->Option<Text> {
 if s==t("true"){Some(t("True"))}else if s==t("false"){Some(t("False"))}else if s==t("null"){Some(t("None"))}
 else if canonical_integer(s).is_some() || dyadic(s).is_some(){Some(s)}else{None}}
pub open spec fn safe(c:char)->bool {' '<=c<='~' && c!='"' && c!='\\'}
pub open spec fn step(p:Parser,c:char)->Parser {
 if p.mode==0 {if c==' '{p}else if c=='{'{Parser{mode:1,..p}}else{Parser{mode:10,..p}}}
 else if p.mode==1 || p.mode==2 {if c==' '{p}else if c=='"'{Parser{mode:3,key:Seq::empty(),value:Seq::empty(),..p}}else if c=='}' && p.mode==1{Parser{mode:9,..p}}else{Parser{mode:10,..p}}}
 else if p.mode==3 {if c=='"'{Parser{mode:4,..p}}else if safe(c){Parser{key:p.key.push(c),..p}}else{Parser{mode:10,..p}}}
 else if p.mode==4 {if c==' '{p}else if c==':'{Parser{mode:5,..p}}else{Parser{mode:10,..p}}}
 else if p.mode==5 {if c==' '{p}else if c=='"'{Parser{mode:6,value:Seq::empty(),..p}}else if c==','||c=='}'{Parser{mode:10,..p}}else{Parser{mode:7,value:seq![c],..p}}}
 else if p.mode==6 {if c=='"'{Parser{mode:8,entries:upsert(p.entries,p.key,p.value),..p}}else if safe(c){Parser{value:p.value.push(c),..p}}else{Parser{mode:10,..p}}}
 else if p.mode==7 {if c==' '||c==','||c=='}' {match bare(p.value){Some(v)=>Parser{mode:if c==' '{8}else if c==','{2}else{9},entries:upsert(p.entries,p.key,v),..p},None=>Parser{mode:10,..p}}}else{Parser{value:p.value.push(c),..p}}}
 else if p.mode==8 {if c==' '{p}else if c==','{Parser{mode:2,..p}}else if c=='}'{Parser{mode:9,..p}}else{Parser{mode:10,..p}}}
 else if p.mode==9 && c==' '{p}else{Parser{mode:10,..p}}
}
pub open spec fn parse(s:Text,p:Parser)->Parser decreases s.len() {
 if s.len()==0{p}else{parse(s.skip(1),step(p,s[0]))}}
pub open spec fn decode(s:Option<Text>)->Seq<Entry> {
 if s.is_none(){seq![]}else{let p=parse(s.unwrap(),initial());if p.mode==9{p.entries}else{seq![]}}
}
pub proof fn lemma_upsert_keys(es:Seq<Entry>,key:Text,value:Text)
 ensures upsert(es,key,value).map_values(key_fn()).to_set()==es.map_values(key_fn()).to_set().insert(key)
 decreases es.len(),
{
 reveal(Seq::to_set);
 if es.len()>0 {assert(seq![es[0].key].to_set() =~= set![es[0].key]);assert(es =~= seq![es[0]]+es.skip(1));assert(es.map_values(key_fn()) =~= seq![es[0].key]+es.skip(1).map_values(key_fn()));seq_to_set_distributes_over_add(seq![es[0].key],es.skip(1).map_values(key_fn()));
 if es[0].key!=key {lemma_upsert_keys(es.skip(1),key,value);assert(upsert(es,key,value).map_values(key_fn()) =~= seq![es[0].key]+upsert(es.skip(1),key,value).map_values(key_fn()));seq_to_set_distributes_over_add(seq![es[0].key],upsert(es.skip(1),key,value).map_values(key_fn()));
 assert(upsert(es,key,value).map_values(key_fn()).to_set()==set![es[0].key].union(upsert(es.skip(1),key,value).map_values(key_fn()).to_set()));
 assert(es.map_values(key_fn()).to_set()==set![es[0].key].union(es.skip(1).map_values(key_fn()).to_set()));
 assert(upsert(es.skip(1),key,value).map_values(key_fn()).to_set()==es.skip(1).map_values(key_fn()).to_set().insert(key));
 }
 else{assert(upsert(es,key,value).map_values(key_fn()) =~= es.map_values(key_fn()));assert(es.map_values(key_fn())[0]==key);assert(es.map_values(key_fn()).to_set().contains(key));}
 }else{assert(es.map_values(key_fn()) =~= Seq::<Text>::empty());assert(upsert(es,key,value).map_values(key_fn()) =~= seq![key]);assert(seq![key].to_set() =~= set![key]);assert(Seq::<Text>::empty().to_set() =~= Set::<Text>::empty());}
 assert(upsert(es,key,value).map_values(key_fn()).to_set() =~= es.map_values(key_fn()).to_set().insert(key));
}
pub proof fn lemma_upsert_unique(es:Seq<Entry>,key:Text,value:Text)
 requires unique(es)
 ensures unique(upsert(es,key,value))
 decreases es.len(),
{if es.len()>0 {
 assert(unique(es.skip(1))) by {assert forall|i:int,j:int|0<=i<j<es.skip(1).len() implies es.skip(1)[i].key!=es.skip(1)[j].key by {assert(es[i+1].key!=es[j+1].key);}}
 if es[0].key!=key{lemma_upsert_unique(es.skip(1),key,value);lemma_upsert_keys(es.skip(1),key,value);}
 assert forall|i:int,j:int|0<=i<j<upsert(es,key,value).len() implies upsert(es,key,value)[i].key!=upsert(es,key,value)[j].key by {
 if es[0].key==key{if i==0 {assert(j<es.len());assert(es[0].key!=es[j].key);}else{assert(es[i].key!=es[j].key);}}
 else if i>0 {assert(upsert(es.skip(1),key,value)[i-1].key!=upsert(es.skip(1),key,value)[j-1].key);}
 else {let ks=upsert(es.skip(1),key,value).map_values(key_fn());assert(ks[j-1]==upsert(es,key,value)[j].key);assert(ks.to_set().contains(ks[j-1]));if es.skip(1).map_values(key_fn()).to_set().contains(es[0].key){let z=choose|z:int|0<=z<es.skip(1).len() && es.skip(1)[z].key==es[0].key;assert(es[z+1].key==es[0].key);}}
 }
 }}
pub proof fn lemma_step_unique(p:Parser,c:char)
 requires unique(p.entries)
 ensures unique(step(p,c).entries)
{lemma_upsert_unique(p.entries,p.key,p.value);if bare(p.value).is_some(){lemma_upsert_unique(p.entries,p.key,bare(p.value).unwrap());}}
pub proof fn lemma_parse_unique(s:Text,p:Parser)
 requires unique(p.entries)
 ensures unique(parse(s,p).entries)
 decreases s.len(),
{if s.len()>0{lemma_step_unique(p,s[0]);lemma_parse_unique(s.skip(1),step(p,s[0]));}}
pub proof fn theorem_raw_json_never_provides_duplicate_keys(s:Option<Text>)
 ensures unique(decode(s))
{if s.is_some(){lemma_parse_unique(s.unwrap(),initial());}}
}

}
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
pub open spec fn emit_label(l:Label,c:Config)->Seq<Quad> {if label_selected(l,c){seq![q(l.graph,uri(l.s,c),t("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),uri(l.label,c))]}else{seq![]}}
pub open spec fn emit_prop(p:Property,rs:Rows,c:Config)->Seq<Quad> {if prop_selected(p,rs,c)&&p.value.is_some(){seq![q(p.graph,uri(p.s,c),property_predicate(p.key,c.base),Term::Literal(literal(p.value.unwrap())))]}else{seq![]}}
pub open spec fn emit_quals(es:Seq<Entry>,e:Edge,pos:nat,c:Config)->Seq<Quad> decreases es.len() {
 if es.len()==0{seq![]}else{(if es[0].key==t("inferred"){seq![]}else{seq![q(e.graph,Term::Blank{position:pos,reifier:true},t("urn:ivg:qualifier/")+es[0].key,Term::Literal(qualifier_literal(es[0].value)))]})+emit_quals(es.skip(1),e,pos,c)}
}
pub open spec fn envelope(e:Edge,pos:nat,c:Config)->Seq<Quad> {
 let st=Term::Blank{position:pos,reifier:false};let rf=Term::Blank{position:pos,reifier:true};
 seq![q(e.graph,st,t("http://www.w3.org/1999/02/22-rdf-syntax-ns#subject"),uri(e.s,c)),q(e.graph,st,t("http://www.w3.org/1999/02/22-rdf-syntax-ns#predicate"),uri(e.p,c)),q(e.graph,st,t("http://www.w3.org/1999/02/22-rdf-syntax-ns#object"),uri(e.o,c)),q(e.graph,rf,t("http://www.w3.org/1999/02/22-rdf-syntax-ns#reifies"),st)]
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
pub open spec fn edge_triple(x:Triple)->bool {matches!(x.o,Term::Iri(_)) && x.p!=t("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")}
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
{assert(emit_edge(e,rs,pos,c)[1]==envelope(e,pos,c)[0]);}
pub proof fn theorem_non_type_uri_count_rule(x:Triple)
 ensures edge_triple(x)==(matches!(x.o,Term::Iri(_)) && x.p!=t("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"))
{}
}
