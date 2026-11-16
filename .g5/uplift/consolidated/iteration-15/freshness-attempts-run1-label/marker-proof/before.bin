// product 3eaa79cf: one triple's rdf_edges row under temporal and explicit writers, read by NDJSON, RDF and Cypher.
use vstd::prelude::*;
#[path="../rdf_reporting/rdf_reporting.rs"] pub mod rr;
#[path="../ndjson_export/qualifier.rs"] pub mod nq;
verus! {
use rr::lexical::{t,digit,canonical_integer,dyadic,literal,qualifier_literal,lower,Literal,mint};
use rr::json::{Entry,Parser,initial,step,parse,decode,upsert,safe,bare};
use rr::{Edge,Rows,Config,Term,Quad,Triple,Report,q,uri,envelope,emit_edge,emit_quals,edge_selected,generated,reported,emit_edges,emit_labels,emit_props,triples,subjects,edge_triple,triple_fn,subject_fn,edge_fn};
pub type Text=Seq<char>;

// ---- raw marker text written by Graph.KG.Adjacency.AssertTemporalRow (%DynamicObject.%ToJSON spelling) ----
pub open spec fn kt()->Text {seq!['t','e','m','p','o','r','a','l']}
pub open spec fn kw()->Text {seq!['w','e','i','g','h','t']}
pub open spec fn head()->Text {seq!['{','"']+kt()+seq!['"',':','t','r','u','e']}
/// The weight's JSON spelling (provider: ObjectScript +pWeight then %ToJSON) is an admitted bare number.
pub open spec fn weight_spelling(w:Text)->bool {
 w.len()>0 && (digit(w[0]) || w[0]=='-') && (canonical_integer(w).is_some() || dyadic(w).is_some())
 && forall|i:int|0<=i<w.len() ==> w[i]!=' ' && w[i]!=',' && w[i]!='}'
}
/// AssertTemporalRow keeps the weight only when it is not 1; 1's canonical spelling is "1".
pub open spec fn unit(w:Text)->bool {w==seq!['1']}
pub open spec fn marker(w:Text)->Text {
 if unit(w){head()+seq!['}']}else{head()+seq![',','"']+kw()+seq!['"',':']+w+seq!['}']}
}

// ---- one triple's row (single default-ekey row; multigraph keys outside this scope) ----
pub enum Row {Absent,Present{quals:Option<Text>}}
/// _adopt_temporal_row: json.loads(quals) is a dict whose "temporal" is True.
pub open spec fn object_marked(quals:Option<Text>)->bool {
 exists|i:int|0<=i<decode(quals).len() && decode(quals)[i].key==kt() && decode(quals)[i].value==seq!['T','r','u','e']
}
/// AssertTemporalRow: INSERT ... WHERE NOT EXISTS any row of the triple.
pub open spec fn temporal_write(r:Row,w:Text)->Row {match r {Row::Absent=>Row::Present{quals:Some(marker(w))},Row::Present{..}=>r}}
/// create_edge: insert when absent; on a duplicate, adopt only a marked row with the call's own qualifiers.
pub open spec fn explicit_write(r:Row,own:Option<Text>)->Row {
 match r {Row::Absent=>Row::Present{quals:own},Row::Present{quals}=>if object_marked(quals){Row::Present{quals:own}}else{r}}
}
/// bulk_create_edges: insert when absent; then _ADOPT_TEMPORAL_ROW_SQL sets NULL on a row whose text starts {"temporal".
pub open spec fn bulk_write(r:Row)->Row {
 match r {Row::Absent=>Row::Present{quals:None},Row::Present{quals}=>if nq::marked(quals){Row::Present{quals:None}}else{r}}
}

// ---- readers ----
/// export_graph_ndjson: a default-graph row is written unless its text starts {"temporal".
pub open spec fn ndjson_line(r:Row)->bool {match r {Row::Absent=>false,Row::Present{quals}=>!nq::marked(quals)}}
/// properties(r): CY_RETYPE_MAP(qualifiers) keeps every decoded key (no marker filter).
pub open spec fn cypher_keys(r:Row)->Seq<Text> {match r {Row::Absent=>seq![],Row::Present{quals}=>decode(quals).map_values(|e:Entry|e.key)}}
pub open spec fn edge_of(r:Row,s:Text,p:Text,o:Text)->Edge {Edge{graph:None,s,p,o,qualifiers:match r {Row::Absent=>None,Row::Present{quals}=>quals}}}
pub open spec fn world(r:Row,s:Text,p:Text,o:Text)->Rows {Rows{labels:seq![],props:seq![],edges:match r {Row::Absent=>seq![],Row::Present{..}=>seq![edge_of(r,s,p,o)]}}}
pub open spec fn all_graphs(base:Text)->Config {Config{graph:None,ids:seq![],labels:seq![],base}}

// ---- parser lemmas over the accepted RDF JSON recognizer ----
pub proof fn lemma_parse_concat(a:Text,b:Text,p:Parser)
 ensures parse(a+b,p)==parse(b,parse(a,p))
 decreases a.len()
{
 if a.len()==0 {assert(a+b=~=b);}
 else {assert((a+b).skip(1)=~=a.skip(1)+b);assert((a+b)[0]==a[0]);lemma_parse_concat(a.skip(1),b,step(p,a[0]));}
}
pub proof fn lemma_key_chars(k:Text,p:Parser)
 requires p.mode==3,forall|i:int|0<=i<k.len() ==> safe(k[i]),
 ensures parse(k,p)==(Parser{key:p.key+k,..p}),
 decreases k.len()
{
 if k.len()==0 {assert(p.key+k=~=p.key);}
 else {let p1=step(p,k[0]);assert(p1==Parser{key:p.key.push(k[0]),..p});lemma_key_chars(k.skip(1),p1);assert(p.key.push(k[0])+k.skip(1)=~=p.key+k);}
}
pub proof fn lemma_value_chars(v:Text,p:Parser)
 requires p.mode==7,forall|i:int|0<=i<v.len() ==> v[i]!=' ' && v[i]!=',' && v[i]!='}',
 ensures parse(v,p)==(Parser{value:p.value+v,..p}),
 decreases v.len()
{
 if v.len()==0 {assert(p.value+v=~=p.value);}
 else {let p1=step(p,v[0]);assert(p1==Parser{value:p.value.push(v[0]),..p});lemma_value_chars(v.skip(1),p1);assert(p.value.push(v[0])+v.skip(1)=~=p.value+v);}
}
proof fn lemma_kt_safe() ensures forall|i:int|0<=i<kt().len() ==> safe(kt()[i]) {}
proof fn lemma_kw_safe() ensures forall|i:int|0<=i<kw().len() ==> safe(kw()[i]) {}
/// Parser state after the shared head `{"temporal":true`.
proof fn lemma_head(p0:Parser)
 requires p0==initial()
 ensures parse(head(),p0)==(Parser{mode:7,key:kt(),value:seq!['t','r','u','e'],entries:seq![]})
{
 let p2=step(step(p0,'{'),'"');assert(p2==Parser{mode:3,key:Seq::<char>::empty(),value:Seq::<char>::empty(),entries:Seq::<Entry>::empty()});
 lemma_kt_safe();lemma_key_chars(kt(),p2);let p3=parse(kt(),p2);assert(p3.key=~=kt());
 let p4=step(p3,'"');let p5=step(p4,':');let p6=step(p5,'t');assert(p6.value=~=seq!['t']);
 let p9=step(step(step(p6,'r'),'u'),'e');assert(p9.value=~=seq!['t','r','u','e']);
 reveal_with_fuel(parse,7);
 assert(seq!['{','"']+kt()+seq!['"',':','t','r','u','e']=~=seq!['{','"']+(kt()+seq!['"',':','t','r','u','e']));
 lemma_parse_concat(seq!['{','"'],kt()+seq!['"',':','t','r','u','e'],p0);
 lemma_parse_concat(kt(),seq!['"',':','t','r','u','e'],p2);
}
proof fn lemma_bare_true() ensures bare(seq!['t','r','u','e'])==Some(seq!['T','r','u','e'])
{reveal_strlit("true");reveal_strlit("True");assert(t("true")=~=seq!['t','r','u','e']);assert(t("True")=~=seq!['T','r','u','e']);}
proof fn lemma_bare_weight(w:Text) requires weight_spelling(w) ensures bare(w)==Some(w)
{reveal_strlit("true");reveal_strlit("false");reveal_strlit("null");assert(w!=t("true") && w!=t("false") && w!=t("null")) by {assert(t("true")[0]=='t');assert(t("false")[0]=='f');assert(t("null")[0]=='n');}}

/// The unit marker's characters decode to one entry; stated over the text itself, not over `marker`.
proof fn lemma_unit_text_decodes()
 ensures decode(Some(head()+seq!['}']))==seq![Entry{key:kt(),value:seq!['T','r','u','e']}],
{
 let p0=initial();lemma_head(p0);lemma_bare_true();
 lemma_parse_concat(head(),seq!['}'],p0);reveal_with_fuel(parse,2);
 assert(upsert(Seq::<Entry>::empty(),kt(),seq!['T','r','u','e'])=~=seq![Entry{key:kt(),value:seq!['T','r','u','e']}]);
}
/// The marker text is decoded from its characters: temporal=True, plus weight=w when w is not 1.
pub proof fn theorem_marker_decodes(w:Text)
 requires weight_spelling(w)
 ensures unit(w) ==> decode(Some(marker(w)))==seq![Entry{key:kt(),value:seq!['T','r','u','e']}],
  !unit(w) ==> decode(Some(marker(w)))==seq![Entry{key:kt(),value:seq!['T','r','u','e']},Entry{key:kw(),value:w}],
{
 let p0=initial();lemma_head(p0);let ph=parse(head(),p0);lemma_bare_true();
 if unit(w) {
  lemma_unit_text_decodes();
 } else {
  let tail=seq![',','"']+kw()+seq!['"',':']+w+seq!['}'];
  lemma_parse_concat(head(),tail,p0);
  let pc=step(ph,',');let e1=seq![Entry{key:kt(),value:seq!['T','r','u','e']}];
  assert(upsert(Seq::<Entry>::empty(),kt(),seq!['T','r','u','e'])=~=e1);
  assert(pc==Parser{mode:2,entries:e1,..ph});
  let pq=step(pc,'"');assert(pq==Parser{mode:3,key:Seq::<char>::empty(),value:Seq::<char>::empty(),entries:e1});
  lemma_kw_safe();lemma_key_chars(kw(),pq);let pk=parse(kw(),pq);assert(pk.key=~=kw());
  let p4=step(pk,'"');let p5=step(p4,':');
  assert(w[0]!=' ' && w[0]!='"' && w[0]!=',' && w[0]!='}');
  let p6=step(p5,w[0]);assert(p6==Parser{mode:7,value:seq![w[0]],..p5});
  lemma_value_chars(w.skip(1),p6);let pv=parse(w.skip(1),p6);assert(pv.value=~=w);
  lemma_bare_weight(w);
  assert(kw()!=kt()) by {assert(kw().len()!=kt().len());}
  let e2=seq![Entry{key:kt(),value:seq!['T','r','u','e']},Entry{key:kw(),value:w}];
  reveal_with_fuel(upsert,2);assert(upsert(e1,kw(),w)=~=e2);
  let pend=step(pv,'}');assert(pend==Parser{mode:9,entries:e2,..pv});
  let a1=seq![',','"'];let a3=seq!['"',':'];let a5=seq!['}'];let w0=seq![w[0]];let wr=w.skip(1);
  assert(w=~=w0+wr);
  assert(marker(w)=~=head()+(a1+(kw()+(a3+(w0+(wr+a5))))));
  reveal_with_fuel(parse,3);
  assert(parse(a1,ph)==pq);assert(parse(a3,pk)==p5);assert(parse(w0,p5)==p6);assert(parse(a5,pv)==pend);
  lemma_parse_concat(head(),a1+(kw()+(a3+(w0+(wr+a5)))),p0);
  lemma_parse_concat(a1,kw()+(a3+(w0+(wr+a5))),ph);
  lemma_parse_concat(kw(),a3+(w0+(wr+a5)),pq);
  lemma_parse_concat(a3,w0+(wr+a5),pk);
  lemma_parse_concat(w0,wr+a5,p5);
  lemma_parse_concat(wr,a5,p6);
  assert(parse(marker(w),p0)==pend);
 }
}
/// Every marker the temporal writer stores is a marked row for both marker readers.
pub proof fn theorem_marker_is_marked_for_both_readers(w:Text)
 requires weight_spelling(w)
 ensures nq::marked(Some(marker(w))),object_marked(Some(marker(w))),
{
 assert(marker(w).subrange(0,11)=~=seq!['{','"','t','e','m','p','o','r','a','l','"']);
 theorem_marker_decodes(w);assert(decode(Some(marker(w)))[0].key==kt());
}

// ---- producer histories ----
pub proof fn theorem_temporal_on_absent_marks(w:Text)
 requires weight_spelling(w)
 ensures temporal_write(Row::Absent,w)==(Row::Present{quals:Some(marker(w))}),
{}
pub proof fn theorem_temporal_never_rewrites_a_row(r:Row,w:Text)
 requires r!=Row::Absent
 ensures temporal_write(r,w)==r,
{}
pub proof fn theorem_explicit_adopts_marked_with_own(w:Text,own:Option<Text>)
 requires weight_spelling(w)
 ensures explicit_write(temporal_write(Row::Absent,w),own)==(Row::Present{quals:own}),
{theorem_marker_is_marked_for_both_readers(w);}
pub proof fn theorem_bulk_adopts_marked_to_null(w:Text)
 requires weight_spelling(w)
 ensures bulk_write(temporal_write(Row::Absent,w))==(Row::Present{quals:None}),
{theorem_marker_is_marked_for_both_readers(w);}
pub proof fn theorem_first_temporal_weight_wins(w1:Text,w2:Text)
 requires weight_spelling(w1),weight_spelling(w2)
 ensures temporal_write(temporal_write(Row::Absent,w1),w2)==(Row::Present{quals:Some(marker(w1))}),
{}
pub proof fn theorem_explicit_first_stays_unmarked(own:Option<Text>,w:Text)
 requires weight_spelling(w)
 ensures temporal_write(explicit_write(Row::Absent,own),w)==(Row::Present{quals:own}),
{}

pub proof fn theorem_explicit_duplicate_keeps_unmarked(own1:Option<Text>,own2:Option<Text>)
 requires !object_marked(own1)
 ensures explicit_write(explicit_write(Row::Absent,own1),own2)==(Row::Present{quals:own1}),
{}
// ---- readers on the same triple ----
pub proof fn theorem_ndjson_omits_marked_includes_adopted(w:Text,own:Option<Text>)
 requires weight_spelling(w),!nq::marked(own)
 ensures !ndjson_line(temporal_write(Row::Absent,w)),ndjson_line(explicit_write(temporal_write(Row::Absent,w),own)),
  ndjson_line(bulk_write(temporal_write(Row::Absent,w))),
{theorem_marker_is_marked_for_both_readers(w);}
pub proof fn theorem_cypher_reports_marker_key(w:Text)
 requires weight_spelling(w)
 ensures cypher_keys(temporal_write(Row::Absent,w)).contains(kt()),
  !cypher_keys(bulk_write(temporal_write(Row::Absent,w))).contains(kt()),
{
 theorem_marker_decodes(w);theorem_marker_is_marked_for_both_readers(w);
 assert(cypher_keys(temporal_write(Row::Absent,w))[0]==kt());
 assert(decode(None)=~=Seq::<Entry>::empty());assert(cypher_keys(bulk_write(temporal_write(Row::Absent,w)))=~=Seq::<Text>::empty());
}
pub open spec fn rdfns(x:Text)->Text {t("http://www.w3.org/1999/02/22-rdf-syntax-ns#")+x}
/// RDF: the marked row gets the reification envelope and a boolean `temporal` qualifier; plain/adopted rows do not.
pub proof fn theorem_rdf_marked_row_is_reified(w:Text,s:Text,p:Text,o:Text,base:Text)
 requires weight_spelling(w)
 ensures ({let r=temporal_write(Row::Absent,w);let c=all_graphs(base);let e=edge_of(r,s,p,o);
   emit_edge(e,world(r,s,p,o),0,c).len()==(if unit(w){6nat}else{7nat})
   && emit_edge(e,world(r,s,p,o),0,c)[5]==q(None,Term::Blank{position:0,reifier:true},t("urn:ivg:qualifier/")+kt(),Term::Literal(Literal::Boolean(true)))
   && emit_edge(e,world(r,s,p,o),0,c).subrange(1,5)==envelope(e,0,c)}),
  ({let r=bulk_write(temporal_write(Row::Absent,w));let c=all_graphs(base);
   emit_edge(edge_of(r,s,p,o),world(r,s,p,o),0,c)==seq![q(None,uri(s,c),mint(p,base),uri(o,c))]}),
{
 let r=temporal_write(Row::Absent,w);let c=all_graphs(base);let e=edge_of(r,s,p,o);let rs=world(r,s,p,o);
 theorem_marker_decodes(w);reveal(emit_edge);assert(edge_selected(e,rs,c));
 let es=decode(e.qualifiers);
 reveal_strlit("inferred");assert(kt()!=t("inferred")) by {assert(kt()[0]!=t("inferred")[0]);}
 assert(kw()!=t("inferred")) by {assert(kw()[0]!=t("inferred")[0]);}
 reveal_strlit("true");reveal_strlit("false");reveal_strlit("007");
 assert(lower(seq!['T','r','u','e'])=~=t("true"));
 assert(canonical_integer(seq!['T','r','u','e']).is_none()) by {reveal_strlit("0");}
 assert(dyadic(seq!['T','r','u','e']).is_none()) by {reveal_strlit(".25");reveal_strlit(".75");reveal_strlit(".5");reveal_strlit(".0");}
 assert(seq!['T','r','u','e']!=t("007")) by {assert(t("007")[0]=='0');}
 assert(literal(seq!['T','r','u','e'])==Literal::Boolean(true));
 assert(qualifier_literal(seq!['T','r','u','e'])==Literal::Boolean(true));
 reveal_with_fuel(emit_quals,3);
 if unit(w) {assert(es.skip(1)=~=Seq::<Entry>::empty());} else {assert(es.skip(1)=~=seq![Entry{key:kw(),value:w}]);assert(es.skip(1).skip(1)=~=Seq::<Entry>::empty());}
 let rb=bulk_write(r);theorem_marker_is_marked_for_both_readers(w);
 assert(decode(Option::<Text>::None)=~=Seq::<Entry>::empty());
 assert(edge_selected(edge_of(rb,s,p,o),world(rb,s,p,o),c));
}
/// The final export report for the one-edge world: unit marker 6 triples, 3 subjects, 4 IRI-object edges; plain 1/1/1.
pub open spec fn rtype()->Text {t("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")}
proof fn lemma_one_edge_generated(r:Row,s:Text,p:Text,o:Text,c:Config)
 requires r!=Row::Absent
 ensures generated(world(r,s,p,o),c)=~=emit_edge(edge_of(r,s,p,o),world(r,s,p,o),0,c),
{
 let w=world(r,s,p,o);assert(w.edges=~=seq![edge_of(r,s,p,o)]);assert(w.edges.skip(1)=~=Seq::<Edge>::empty());
 reveal_with_fuel(emit_edges,2);reveal_with_fuel(emit_labels,1);reveal_with_fuel(emit_props,1);
}
pub proof fn theorem_rdf_report_counts(s:Text,p:Text,o:Text,base:Text)
 requires mint(p,base)!=rtype()
 ensures ({let r=temporal_write(Row::Absent,seq!['1']);reported(world(r,s,p,o),all_graphs(base))==Report{triples:6,nodes:3,edges:4}}),
  ({let r=explicit_write(Row::Absent,None);reported(world(r,s,p,o),all_graphs(base))==Report{triples:1,nodes:1,edges:1}}),
{
 let c=all_graphs(base);
 reveal_strlit("http://www.w3.org/1999/02/22-rdf-syntax-ns#type");reveal_strlit("http://www.w3.org/1999/02/22-rdf-syntax-ns#");
 reveal_strlit("urn:ivg:qualifier/");
 // plain row: one quad
 let rp=explicit_write(Row::Absent,None);let ep=edge_of(rp,s,p,o);let wp=world(rp,s,p,o);
 lemma_one_edge_generated(rp,s,p,o,c);
 reveal(emit_edge);assert(decode(Option::<Text>::None)=~=Seq::<Entry>::empty());assert(edge_selected(ep,wp,c));
 let x=q(None,uri(s,c),mint(p,base),uri(o,c));let gp=generated(wp,c);assert(gp=~=seq![x]);
 assert(gp.map_values(triple_fn())=~=seq![x.triple]);seq![x.triple].unique_seq_to_set();
 assert(gp.map_values(subject_fn())=~=seq![x.triple.s]);seq![x.triple.s].unique_seq_to_set();
 assert(edge_triple(x.triple));
 assert(seq![x.triple].filter(edge_fn())=~=seq![x.triple]) by {reveal_with_fuel(Seq::<_>::filter,2);assert(seq![x.triple].drop_last()=~=Seq::<Triple>::empty());}
 // marked row with unit weight
 let one=seq!['1'];
 assert(weight_spelling(one)) by {reveal_strlit("0");reveal_with_fuel(rr::lexical::digits,2);assert(one.skip(1)=~=Seq::<char>::empty());}
 let r=temporal_write(Row::Absent,one);let e=edge_of(r,s,p,o);let w=world(r,s,p,o);
 // the producer's text for weight 1, from marker's own definition (no call to a marker-level contract)
 assert(unit(one));assert(r==Row::Present{quals:Some(head()+seq!['}'])});
 lemma_one_edge_generated(r,s,p,o,c);lemma_unit_text_decodes();
 let g=generated(w,c);reveal(emit_edge);assert(edge_selected(e,w,c));
 reveal_strlit("inferred");assert(kt()!=t("inferred")) by {assert(kt()[0]!=t("inferred")[0]);}
 reveal_strlit("true");reveal_strlit("false");reveal_strlit("007");
 assert(lower(seq!['T','r','u','e'])=~=t("true"));
 assert(canonical_integer(seq!['T','r','u','e']).is_none()) by {reveal_strlit("0");}
 assert(dyadic(seq!['T','r','u','e']).is_none()) by {reveal_strlit(".25");reveal_strlit(".75");reveal_strlit(".5");reveal_strlit(".0");}
 assert(seq!['T','r','u','e']!=t("007")) by {assert(t("007")[0]=='0');}
 assert(qualifier_literal(seq!['T','r','u','e'])==Literal::Boolean(true));
 reveal_with_fuel(emit_quals,2);let es=decode(e.qualifiers);assert(es.skip(1)=~=Seq::<Entry>::empty());
 let st=Term::Blank{position:0,reifier:false};let rf=Term::Blank{position:0,reifier:true};
 let spo=x.triple;let ts=Triple{s:st,p:rdfns(seq!['s','u','b','j','e','c','t']),o:uri(s,c)};
 let tp=Triple{s:st,p:rdfns(seq!['p','r','e','d','i','c','a','t','e']),o:uri(p,c)};
 let to=Triple{s:st,p:rdfns(seq!['o','b','j','e','c','t']),o:uri(o,c)};
 let tr=Triple{s:rf,p:rdfns(seq!['r','e','i','f','i','e','s']),o:st};
 let tq=Triple{s:rf,p:t("urn:ivg:qualifier/")+kt(),o:Term::Literal(Literal::Boolean(true))};
 reveal_strlit("http://www.w3.org/1999/02/22-rdf-syntax-ns#subject");reveal_strlit("http://www.w3.org/1999/02/22-rdf-syntax-ns#predicate");
 reveal_strlit("http://www.w3.org/1999/02/22-rdf-syntax-ns#object");reveal_strlit("http://www.w3.org/1999/02/22-rdf-syntax-ns#reifies");
 assert(t("http://www.w3.org/1999/02/22-rdf-syntax-ns#subject")=~=rdfns(seq!['s','u','b','j','e','c','t']));
 assert(t("http://www.w3.org/1999/02/22-rdf-syntax-ns#predicate")=~=rdfns(seq!['p','r','e','d','i','c','a','t','e']));
 assert(t("http://www.w3.org/1999/02/22-rdf-syntax-ns#object")=~=rdfns(seq!['o','b','j','e','c','t']));
 assert(t("http://www.w3.org/1999/02/22-rdf-syntax-ns#reifies")=~=rdfns(seq!['r','e','i','f','i','e','s']));
 assert(g.map_values(triple_fn())=~=seq![spo,ts,tp,to,tr,tq]);
 assert(ts.p!=tp.p && ts.p!=to.p && tp.p!=to.p) by {assert(ts.p.len()!=tp.p.len());assert(ts.p.len()!=to.p.len());assert(tp.p.len()!=to.p.len());}
 assert(tr.p!=tq.p) by {assert(tr.p.len()!=tq.p.len());}
 assert(seq![spo,ts,tp,to,tr,tq].no_duplicates());seq![spo,ts,tp,to,tr,tq].unique_seq_to_set();
 assert(g.map_values(subject_fn())=~=seq![spo.s,st,st,st,rf,rf]);
 assert(seq![spo.s,st,st,st,rf,rf].to_set()=~=seq![spo.s,st,rf].to_set()) by {
  assert forall|y:Term| seq![spo.s,st,st,st,rf,rf].contains(y) <==> seq![spo.s,st,rf].contains(y) by {
   if seq![spo.s,st,rf].contains(y) {let k=choose|k:int|0<=k<3 && seq![spo.s,st,rf][k]==y; if k==0 {assert(seq![spo.s,st,st,st,rf,rf][0]==y);} else if k==1 {assert(seq![spo.s,st,st,st,rf,rf][1]==y);} else {assert(seq![spo.s,st,st,st,rf,rf][4]==y);}}
  }
 }
 assert(seq![spo.s,st,rf].no_duplicates());seq![spo.s,st,rf].unique_seq_to_set();
 assert(rtype()!=ts.p && rtype()!=tp.p && rtype()!=to.p) by {assert(rtype().len()!=ts.p.len());assert(rtype().len()!=tp.p.len());assert(rtype().len()!=to.p.len());}
 assert(edge_triple(spo) && edge_triple(ts) && edge_triple(tp) && edge_triple(to) && !edge_triple(tr) && !edge_triple(tq));
 assert(seq![spo,ts,tp,to,tr,tq].filter(edge_fn())=~=seq![spo,ts,tp,to]) by {
  reveal_with_fuel(Seq::<_>::filter,7);
  let a=seq![spo,ts,tp,to,tr,tq];
  assert(a.drop_last()=~=seq![spo,ts,tp,to,tr]);assert(a.drop_last().drop_last()=~=seq![spo,ts,tp,to]);
  assert(seq![spo,ts,tp,to].drop_last()=~=seq![spo,ts,tp]);assert(seq![spo,ts,tp].drop_last()=~=seq![spo,ts]);
  assert(seq![spo,ts].drop_last()=~=seq![spo]);assert(seq![spo].drop_last()=~=Seq::<Triple>::empty());
 }
 assert(seq![spo,ts,tp,to].no_duplicates());seq![spo,ts,tp,to].unique_seq_to_set();
}
}
