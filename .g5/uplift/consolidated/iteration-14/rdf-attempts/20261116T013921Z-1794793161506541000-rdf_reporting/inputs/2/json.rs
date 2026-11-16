use vstd::prelude::*;
use super::lexical::*;
verus! {
pub struct Entry {pub key:Text,pub value:Text}
pub open spec fn upsert(es:Seq<Entry>,key:Text,value:Text)->Seq<Entry> decreases es.len() {
 if es.len()==0{seq![Entry{key,value}]}else if es[0].key==key{seq![Entry{key,value}]+es.skip(1)}else{seq![es[0]]+upsert(es.skip(1),key,value)}}
pub open spec fn unique(es:Seq<Entry>)->bool {es.map_values(|e:Entry|e.key).no_duplicates()}
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
 ensures upsert(es,key,value).map_values(|e:Entry|e.key).to_set()==es.map_values(|e:Entry|e.key).to_set().insert(key)
 decreases es.len(),
{if es.len()>0 && es[0].key!=key{lemma_upsert_keys(es.skip(1),key,value);}}
pub proof fn lemma_upsert_unique(es:Seq<Entry>,key:Text,value:Text)
 requires unique(es)
 ensures unique(upsert(es,key,value))
 decreases es.len(),
{if es.len()>0 && es[0].key!=key{lemma_upsert_unique(es.skip(1),key,value);lemma_upsert_keys(es.skip(1),key,value);}}
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
