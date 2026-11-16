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
 match canonical_integer(prefix){Some(n)=>if -1000<=n<=1000 {Some(Decimal{n:n*(den as int)+(if n<0{-part}else{part}),d:den,spelling:s})}else{None},None=>None}}
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
pub open spec fn plain(s:Text)->bool {s.len()==0 || (s.len()>0 && (('a'<=s[0]<='z') || ('A'<=s[0]<='Z')) && lower(s)!=t("nan") && lower(s)!=t("inf") && lower(s)!=t("infinity"))}
pub open spec fn admitted(s:Text)->bool {canonical_integer(s).is_some() || dyadic(s).is_some() || s==t("007") || plain(s)}
pub open spec fn mint(s:Text,base:Text)->Text {
 if starts(s,t("http://"))||starts(s,t("https://"))||starts(s,t("urn:"))||starts(s,t("ftp://")){s}else{base+s}}
pub open spec fn property_predicate(s:Text,base:Text)->Text {
 if starts(s,t("http://"))||starts(s,t("https://"))||starts(s,t("urn:")){mint(s,base)}else{t("urn:ivg:prop/")+s}}
pub proof fn theorem_canonical_integer_is_derived(s:Text,n:int)
 requires canonical_integer(s)==Some(n)
 ensures literal(s)==Literal::Integer{value:n,spelling:s}
{}
pub proof fn theorem_dyadic_is_derived(s:Text,d:Decimal)
 requires canonical_integer(s).is_none(),dyadic(s)==Some(d)
 ensures literal(s)==Literal::Decimal(d),d.d==1||d.d==2||d.d==4,-4003<=d.n<=4003,d.spelling==s
{}
pub proof fn theorem_falsey_qualifier_fallback(s:Text)
 ensures !truth(literal(s)) ==> qualifier_literal(s)==Literal::Plain(s),truth(literal(s)) ==> qualifier_literal(s)==literal(s)
{}
pub proof fn theorem_node_property_prefixes_differ(base:Text)
 ensures mint(t("ftp://x"),base)==t("ftp://x"),property_predicate(t("ftp://x"),base)==t("urn:ivg:prop/ftp://x")
{}
pub proof fn theorem_false_and_zero_are_not_property_literals()
 ensures literal(t("false"))==Literal::Boolean(false),qualifier_literal(t("false"))==Literal::Plain(t("false")),
 literal(t("0"))==Literal::Integer{value:0,spelling:t("0")},qualifier_literal(t("0"))==Literal::Plain(t("0"))
{reveal_with_fuel(digits,2);}
}
