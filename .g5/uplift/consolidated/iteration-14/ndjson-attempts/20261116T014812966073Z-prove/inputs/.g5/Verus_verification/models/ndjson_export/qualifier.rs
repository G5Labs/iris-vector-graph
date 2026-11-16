// Raw ordinary ASCII qualifier fragment. No caller-supplied parse map/truthiness answer.
use vstd::prelude::*;
verus! {
pub enum Qual{Omitted,Field(nat)}
pub open spec fn digit(c:char)->Option<nat>{if '0'<=c<='9'{Some((c as u32-'0' as u32) as nat)}else{None}}
pub open spec fn digits(s:Seq<char>)->Option<nat> decreases s.len(){
 if s.len()==0{None}else{let d=digit(s.last());if d.is_none(){None}else if s.len()==1{d}else{let p=digits(s.drop_last());if p.is_some(){Some(10*p.unwrap()+d.unwrap())}else{None}}}}
pub open spec fn number(s:Seq<char>)->bool{s.len()>0&&(s.len()==1||s[0]!='0')&&digits(s).is_some()}
pub open spec fn qtext(s:Seq<char>)->Seq<char>{seq!['{','"','q','"',':']+s+seq!['}']}
pub open spec fn decode(raw:Option<Seq<char>>)->Option<Qual>{
 if raw.is_none(){Some(Qual::Omitted)}else{let s=raw.unwrap();if s.len()==0||s==seq!['{','}']{Some(Qual::Omitted)}
 else if s.len()>=7&&s[0]=='{'&&s[1]=='"'&&s[2]=='q'&&s[3]=='"'&&s[4]==':'&&s.last()=='}'{let ns=s.subrange(5,s.len() as int-1);if number(ns){Some(Qual::Field(digits(ns).unwrap()))}else{None}}else{None}}}
pub open spec fn marked(raw:Option<Seq<char>>)->bool{raw.is_some()&&raw.unwrap().len()>=11&&raw.unwrap().subrange(0,11)==seq!['{','"','t','e','m','p','o','r','a','l','"']}
pub proof fn lemma_qtext_layout(s:Seq<char>)
 ensures qtext(s).len()==s.len()+6,qtext(s).subrange(5,qtext(s).len() as int-1)==s,qtext(s)[0]=='{',qtext(s)[1]=='"',qtext(s)[2]=='q',qtext(s)[3]=='"',qtext(s)[4]==':',qtext(s).last()=='}',
 {assert(qtext(s).subrange(5,qtext(s).len() as int-1)=~=s);}
pub proof fn theorem_raw_q_number(s:Seq<char>)
 requires number(s),
 ensures decode(Some(qtext(s)))==Some(Qual::Field(digits(s).unwrap())),!marked(Some(qtext(s))),
 {lemma_qtext_layout(s);}
pub proof fn theorem_empty_absent_qualifiers_omit()
 ensures decode(None)==Some(Qual::Omitted),decode(Some(seq![]))==Some(Qual::Omitted),decode(Some(seq!['{','}']))==Some(Qual::Omitted),{}
pub proof fn theorem_zero_is_nonempty_object()
 ensures decode(Some(seq!['{','"','q','"',':','0','}']))==Some(Qual::Field(0)),
 {reveal_with_fuel(digits,2);}
pub proof fn theorem_raw_digits_not_supplied_result(a:char,b:char)
 requires digit(a).is_some(),digit(b).is_some(),a!='0',
 ensures decode(Some(qtext(seq![a,b])))==Some(Qual::Field(10*digit(a).unwrap()+digit(b).unwrap())),
 {reveal_with_fuel(digits,3);theorem_raw_q_number(seq![a,b]);}
pub proof fn theorem_leading_zero_outside_json_number()
 ensures decode(Some(qtext(seq!['0','1']))).is_none(),
 {lemma_qtext_layout(seq!['0','1']);}
pub proof fn theorem_marked_is_raw_prefix(s:Seq<char>)
 ensures marked(Some(seq!['{','"','t','e','m','p','o','r','a','l','"']+s)),
 {assert((seq!['{','"','t','e','m','p','o','r','a','l','"']+s).subrange(0,11)=~=seq!['{','"','t','e','m','p','o','r','a','l','"']);}
}
