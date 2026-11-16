// product 3eaa79cf: Cypher WHERE equality of a stored property with a boolean or integer literal, node vs relationship,
// against the RETURN readers of the accepted node_read and rel_prop_text models.
//   translator.py _stored_bool_in / bool_spellings_sql (TRUE_SPELLINGS, FALSE_SPELLINGS in prop_values.py:87-88),
//   _node_number_eq_sql (stored-number test + numeric equality), _number_eq_sql (relationship text in the number's spellings).
use vstd::prelude::*;
#[path="../node_read/node_read.rs"] pub mod nr;
#[path="../rel_prop_text/rel_prop_text.rs"] pub mod rp;
verus! {
pub type Text=Seq<char>;
pub enum Lit {Bool(bool),Int(int)}

// ---- spellings ----
pub open spec fn digit_char(d:int)->char {((d+48) as u32) as char}
pub open spec fn nat_text(n:nat)->Text decreases n {if n<10 {seq![digit_char(n as int)]} else {nat_text(n/10)+seq![digit_char((n%10) as int)]}}
/// Canonical text of an integer (Python str(int), ObjectScript canonical integer).
pub open spec fn num_text(n:int)->Text {if n<0 {seq!['-']+nat_text((-n) as nat)} else {nat_text(n as nat)}}
pub open spec fn true_spellings()->Seq<Text> {seq![seq!['t','r','u','e'],seq!['1'],seq!['T','r','u','e']]}
pub open spec fn false_spellings()->Seq<Text> {seq![seq!['f','a','l','s','e'],seq!['0'],seq!['F','a','l','s','e']]}
pub open spec fn spellings(b:bool)->Seq<Text> {if b {true_spellings()} else {false_spellings()}}

// ---- node property: rdf_props.val holds a number or text (node_read's Stored) ----
/// Providers for a stored $DOUBLE (node_read keeps its payload abstract): its canonical text and numeric equality
/// with an integer literal. Uninterpreted; no axiom is assumed about them.
pub uninterp spec fn double_text(payload:int)->Text;
pub uninterp spec fn double_equals_int(payload:int,m:int)->bool;
/// SQL `val IN ('true','1','True')`: a text compares as text; a stored number compares through its canonical text
/// (provider premise, observed natively). Big integers are stored as text by the writer and never reach here.
pub open spec fn node_matches_spelling(s:nr::Stored,t:Text)->bool {
 match s {nr::Stored::Text(x)=>x==t,nr::Stored::Number{payload,double}=>if double {double_text(payload)==t} else {num_text(payload)==t},nr::Stored::BigText(_)=>false}
}
pub open spec fn node_where_eq(s:nr::Stored,l:Lit)->bool {
 match l {
  // SQL `val IN (<three spellings>)`
  Lit::Bool(b)=>node_matches_spelling(s,spellings(b)[0]) || node_matches_spelling(s,spellings(b)[1]) || node_matches_spelling(s,spellings(b)[2]),
  // _node_number_eq_sql: the row must hold a stored number of that value (4.7.0 row 24)
  Lit::Int(m)=>match s {nr::Stored::Number{payload,double}=>if double {double_equals_int(payload,m)} else {payload==m},_=>false},
 }
}
/// RETURN n.p: the accepted node_read reader.
pub open spec fn node_return(s:nr::Stored)->nr::Value {nr::read(nr::cy_typed(s))}

// ---- relationship property: one JSON member of qualifiers ----
pub enum Json {Num(int),Str(Text),Bool(bool)}
/// JSON_VALUE text read by WHERE (provider premise, observed natively): a JSON boolean reads as 1 or 0. JSON floats
/// are outside this domain: JSON_VALUE keeps a whole float's own spelling (`1.0`), observed in the binding.
pub open spec fn json_value(j:Json)->Text {match j {Json::Num(n)=>num_text(n),Json::Str(t)=>t,Json::Bool(b)=>if b {seq!['1']} else {seq!['0']}}}
/// The text RETURN decodes (CY_REL_PROP's JSON form): a JSON boolean reads as true or false.
pub open spec fn return_text(j:Json)->Text {match j {Json::Num(n)=>num_text(n),Json::Str(t)=>t,Json::Bool(b)=>if b {rp::tru()} else {rp::fals()}}}
pub open spec fn rel_where_eq(j:Json,l:Lit)->bool {
 match l {
  Lit::Bool(b)=>spellings(b).contains(json_value(j)),
  // _number_eq_sql / _number_texts: the text is the integer's canonical text or its float twin's, `m.0`
  Lit::Int(m)=>json_value(j)==num_text(m) || json_value(j)==num_text(m)+seq!['.','0'],
 }
}
/// RETURN r.p: the accepted rel_prop_text as-built decoder (ordinary scalars are not list/map text).
pub open spec fn rel_return(j:Json)->rp::Val {rp::as_built(return_text(j),false)}

// ---- openCypher equality on the value RETURN reads ----
pub open spec fn typed_node_eq(v:nr::Value,l:Lit)->bool {match l {Lit::Bool(b)=>v==nr::Value::Bool(b),Lit::Int(m)=>v==nr::Value::Integer(m)}}

// ---- spelling lemmas ----
proof fn lemma_digit_char(d:int) requires 0<=d<10 ensures '0'<=digit_char(d)<='9',d==0 <==> digit_char(d)=='0',d==1 <==> digit_char(d)=='1' {}
proof fn lemma_nat_text_shape(n:nat)
 ensures nat_text(n).len()>=1,forall|i:int|0<=i<nat_text(n).len() ==> '0'<=#[trigger] nat_text(n)[i]<='9',n>=10 ==> nat_text(n).len()>=2,
 decreases n
{ if n>=10 {lemma_nat_text_shape(n/10);lemma_digit_char((n%10) as int);} else {lemma_digit_char(n as int);} }
/// The canonical text of an integer is "1" only for 1 and "0" only for 0.
pub proof fn lemma_num_text_one_char(n:int)
 ensures num_text(n)==seq!['1'] <==> n==1, num_text(n)==seq!['0'] <==> n==0,
{
 if n<0 {lemma_nat_text_shape((-n) as nat);assert(num_text(n).len()>=2);}
 else {lemma_nat_text_shape(n as nat);
  if n<10 {lemma_digit_char(n);assert(num_text(n)=~=seq![digit_char(n)]);
   if n==1 {assert(num_text(n)=~=seq!['1']);} if n==0 {assert(num_text(n)=~=seq!['0']);}
   assert(num_text(n)[0]==digit_char(n));if num_text(n)==seq!['1'] {assert(num_text(n)[0]=='1');} if num_text(n)==seq!['0'] {assert(num_text(n)[0]=='0');}
  } else {assert(num_text(n).len()>=2);}}
}
proof fn lemma_num_text_digits(n:int) ensures num_text(n).len()>=1,num_text(n)[0]=='-' || ('0'<=num_text(n)[0]<='9')
{ if n<0 {lemma_nat_text_shape((-n) as nat);} else {lemma_nat_text_shape(n as nat);} }

// ---- theorems: nodes ----
/// Exact: a node property equals `true` iff it is the text true, 1 or True, or the stored integer 1.
pub proof fn theorem_node_true_exact(s:nr::Stored)
 requires !(s matches nr::Stored::Number{double:true,..}),
 ensures node_where_eq(s,Lit::Bool(true)) <==> (s==nr::Stored::Text(seq!['t','r','u','e']) || s==nr::Stored::Text(seq!['1'])
   || s==nr::Stored::Text(seq!['T','r','u','e']) || s==(nr::Stored::Number{payload:1,double:false})),
{
 let sp=spellings(true);
 assert(sp[0]=~=seq!['t','r','u','e']);assert(sp[1]=~=seq!['1']);assert(sp[2]=~=seq!['T','r','u','e']);
 match s {
  nr::Stored::Number{payload,double}=>{
   lemma_num_text_one_char(payload);lemma_num_text_digits(payload);
   if node_matches_spelling(s,sp[0]) {assert(num_text(payload)[0]=='t');}
   if node_matches_spelling(s,sp[2]) {assert(num_text(payload)[0]=='T');}
   if s==(nr::Stored::Number{payload:1,double:false}) {lemma_num_text_one_char(1);assert(node_matches_spelling(s,sp[1]));}
  },
  nr::Stored::Text(x)=>{
   if x==seq!['t','r','u','e'] {assert(node_matches_spelling(s,sp[0]));}
   if x==seq!['1'] {assert(node_matches_spelling(s,sp[1]));}
   if x==seq!['T','r','u','e'] {assert(node_matches_spelling(s,sp[2]));}
  },
  nr::Stored::BigText(_)=>{},
 }
}
/// WHERE and RETURN disagree: the stored integer 1 and the text "1" equal `true`, but RETURN reads 1 and "1".
pub proof fn theorem_node_where_return_disagree()
 ensures node_where_eq(nr::Stored::Number{payload:1,double:false},Lit::Bool(true)),
  node_return(nr::Stored::Number{payload:1,double:false})==nr::Value::Integer(1),
  !typed_node_eq(node_return(nr::Stored::Number{payload:1,double:false}),Lit::Bool(true)),
  node_where_eq(nr::Stored::Text(seq!['1']),Lit::Bool(true)),!node_where_eq(nr::Stored::Text(seq!['1']),Lit::Int(1)),
  node_return(nr::Stored::Text(seq!['1']))==nr::Value::Text(seq!['1']),
  node_where_eq(nr::Stored::Number{payload:0,double:false},Lit::Bool(false)),
{
 // self-contained: from the definitions, not from theorem_node_true_exact's contract
 lemma_num_text_one_char(1);assert(spellings(true)[1]=~=seq!['1']);
 assert(node_matches_spelling(nr::Stored::Number{payload:1,double:false},spellings(true)[1]));
 assert(node_matches_spelling(nr::Stored::Text(seq!['1']),spellings(true)[1]));
 lemma_num_text_one_char(0);assert(spellings(false)[1]=~=seq!['0']);assert(node_matches_spelling(nr::Stored::Number{payload:0,double:false},spellings(false)[1]));
 assert(seq!['1']!=nr::bool_text(true));assert(seq!['1']!=nr::bool_text(false));
}
/// A node boolean (stored as the text true) does not equal the integer 1, and RETURN reads it as true.
pub proof fn theorem_node_bool_not_integer(m:int)
 ensures !node_where_eq(nr::write(nr::Input::Bool(true)),Lit::Int(m)),node_where_eq(nr::write(nr::Input::Bool(true)),Lit::Bool(true)),
  node_return(nr::write(nr::Input::Bool(true)))==nr::Value::Bool(true),
{theorem_node_true_exact(nr::write(nr::Input::Bool(true)));}
/// Integer equality on a node needs a stored number of that value; no text equals an integer.
pub proof fn theorem_node_integer_needs_stored_number(t:Text,n:int,m:int)
 ensures !node_where_eq(nr::Stored::Text(t),Lit::Int(m)),node_where_eq(nr::Stored::Number{payload:n,double:false},Lit::Int(m))==(n==m),
  node_where_eq(nr::Stored::Number{payload:n,double:true},Lit::Int(m))==double_equals_int(n,m),
{}
/// Outside the legacy spellings, boolean equality on a node agrees with openCypher equality on the value RETURN reads.
pub proof fn theorem_node_bool_agrees_outside_legacy(s:nr::Stored)
 requires !(s matches nr::Stored::Number{double:true,..}),s!=nr::Stored::Text(seq!['1']),s!=nr::Stored::Text(seq!['T','r','u','e']),s!=(nr::Stored::Number{payload:1,double:false}),
  !(s matches nr::Stored::Text(x) && x.len()>0 && x[0]=='\u{1}'),
 ensures node_where_eq(s,Lit::Bool(true))==typed_node_eq(node_return(s),Lit::Bool(true)),
{
 theorem_node_true_exact(s);
 match s {nr::Stored::Text(x)=>{if x==nr::bool_text(true) {assert(x==seq!['t','r','u','e']);}},_=>{}}
}

// ---- theorems: relationships ----
/// Relationship booleans equal integers: JSON true equals 1 and false equals 0 in WHERE, while RETURN reads a boolean.
pub proof fn theorem_rel_bool_equals_integer()
 ensures rel_where_eq(Json::Bool(true),Lit::Int(1)),rel_where_eq(Json::Bool(false),Lit::Int(0)),
  rel_return(Json::Bool(true))==rp::Val::Bool(true),
  !node_where_eq(nr::write(nr::Input::Bool(true)),Lit::Int(1)),
{lemma_num_text_one_char(1);lemma_num_text_one_char(0);theorem_node_bool_not_integer(1);}
/// Relationship integer 1 and string "1" equal `true`; RETURN reads both as integers.
pub proof fn theorem_rel_integer_equals_true()
 ensures rel_where_eq(Json::Num(1),Lit::Bool(true)),rel_where_eq(Json::Str(seq!['1']),Lit::Bool(true)),
  rel_return(Json::Num(1))==rp::Val::Int,rel_return(Json::Str(seq!['1']))==rp::Val::Int,
{
 lemma_num_text_one_char(1);assert(true_spellings()[1]==seq!['1']);
 assert(seq!['1'].drop_first()=~=Seq::<char>::empty());assert(rp::unsigned(seq!['1'])=~=seq!['1']);assert(rp::int_text(seq!['1'],true));
 assert(seq!['1']!=rp::tru());assert(seq!['1']!=rp::fals());
}
/// A relationship text spelling the integer's float twin equals the integer; RETURN reads it as a float.
pub proof fn theorem_rel_twin_spelling_equals_integer()
 ensures rel_where_eq(Json::Str(seq!['1','2','.','0']),Lit::Int(12)),!node_where_eq(nr::Stored::Text(seq!['1','2','.','0']),Lit::Int(12)),
  rel_return(Json::Str(seq!['1','2','.','0']))==rp::Val::Float,
{
 reveal_with_fuel(nat_text,2);assert(nat_text(12)=~=seq!['1','2']);assert(num_text(12)+seq!['.','0']=~=seq!['1','2','.','0']);
 let u=seq!['1','2','.','0'];assert(rp::unsigned(u)=~=u);
 assert(u.subrange(0,2)=~=seq!['1','2']);assert(u.subrange(3,4)=~=seq!['0']);assert(seq!['1','2'].drop_first()=~=seq!['2']);
 assert(rp::int_digits(u.subrange(0,2),true));assert(rp::digits(u.subrange(3,4),true));assert(u[2]=='.');
 assert(rp::float_text(u,true));
 assert(!rp::int_text(u,true)) by {assert(rp::unsigned(u).drop_first()[1]=='.');assert(!rp::py_digit('.'));}
 assert(!rp::py_match_int(u)) by {assert(u.last()!='\n');}
 assert(rp::py_match_float(u));assert(u!=rp::tru());assert(u!=rp::fals());
}
/// The same user string "12" equals 12 on a relationship but not on a node; each kind's RETURN agrees with its WHERE.
pub proof fn theorem_string_integer_kind_asymmetry()
 ensures rel_where_eq(Json::Str(seq!['1','2']),Lit::Int(12)),!node_where_eq(nr::Stored::Text(seq!['1','2']),Lit::Int(12)),
  rel_return(Json::Str(seq!['1','2']))==rp::Val::Int,node_return(nr::Stored::Text(seq!['1','2']))==nr::Value::Text(seq!['1','2']),
{
 reveal_with_fuel(nat_text,2);assert(nat_text(12)=~=seq!['1','2']);
 assert(seq!['1','2'].drop_first()=~=seq!['2']);assert(rp::unsigned(seq!['1','2'])=~=seq!['1','2']);assert(rp::digits(seq!['2'],true));assert(rp::int_text(seq!['1','2'],true));
 assert(seq!['1','2']!=rp::tru());assert(seq!['1','2']!=rp::fals());
 assert(seq!['1','2']!=nr::bool_text(true));assert(seq!['1','2']!=nr::bool_text(false));
}

// ---- ordering against an integer literal (`<`, `>`, `<=`, `>=`): _translate_boolean_expression's `_as_number` ----
pub enum Ord {Lt,Gt,Le,Ge}
pub open spec fn holds(o:Ord,a:real,b:real)->bool {match o {Ord::Lt=>a<b,Ord::Gt=>a>b,Ord::Le=>a<=b,Ord::Ge=>a>=b}}
/// Provider: IRIS `CAST(<text> AS DOUBLE)`. Uninterpreted; the binding observes it (letter-initial text gives 0).
pub uninterp spec fn cast_double(t:Text)->real;
/// Provider: a stored double's numeric value.
pub uninterp spec fn double_value(payload:int)->real;
/// Node: `_stored_number_value` gives the value only for a stored number, else SQL NULL, so the comparison drops the row.
pub open spec fn node_where_ord(s:nr::Stored,o:Ord,m:int)->bool {
 match s {nr::Stored::Number{payload,double}=>holds(o,if double {double_value(payload)} else {payload as real},m as real),_=>false}
}
/// Relationship: `CAST(JSON_VALUE(qualifiers, '$.p') AS DOUBLE)` against the literal.
pub open spec fn rel_where_ord(j:Json,o:Ord,m:int)->bool {holds(o,cast_double(json_value(j)),m as real)}

/// A node text never orders against a number, whatever it spells.
pub proof fn theorem_node_text_never_orders(t:Text,o:Ord,m:int)
 ensures !node_where_ord(nr::Stored::Text(t),o,m),
{}
/// A stored node integer orders by its value.
pub proof fn theorem_node_integer_orders_by_value(n:int,o:Ord,m:int)
 ensures node_where_ord(nr::Stored::Number{payload:n,double:false},o,m)==holds(o,n as real,m as real),
{}
/// If IRIS casts a relationship text to 0, that text is below every positive integer, while RETURN reads it as the text.
pub proof fn theorem_rel_text_orders_as_cast(t:Text,m:int)
 requires cast_double(t)==0real,m>0,t.len()>0,'a'<=t[0]<='z',t!=rp::tru(),t!=rp::fals(),
 ensures rel_where_ord(Json::Str(t),Ord::Lt,m),!node_where_ord(nr::Stored::Text(t),Ord::Lt,m),
  rel_return(Json::Str(t))==rp::Val::Str(t),
{
 assert(!rp::shaped(t));
 assert(t[0]!='-');assert(rp::unsigned(t)=~=t);
 assert(!rp::int_text(t,true)) by {assert(rp::unsigned(t)[0]==t[0]);assert(!('1'<=t[0]<='9') && t[0]!='0');}
 assert(!rp::py_match_int(t)) by {if t.len()>=2 && t.last()=='\n' {let u=t.drop_last();assert(u[0]==t[0]);assert(u[0]!='-');assert(rp::unsigned(u)=~=u);assert(rp::unsigned(u)[0]==t[0]);} if t.len()==1 && t.last()=='\n' {assert(t[0]=='\n');}}
 assert(!rp::float_text(t,true)) by {assert(rp::unsigned(t)==t);if rp::float_text(t,true) {let k=choose|k:int| 0<k<rp::unsigned(t).len()-1 && #[trigger] rp::unsigned(t)[k]=='.' && rp::int_digits(rp::unsigned(t).subrange(0,k),true) && rp::digits(rp::unsigned(t).subrange(k+1,rp::unsigned(t).len() as int),true) && rp::unsigned(t).subrange(k+1,rp::unsigned(t).len() as int).len()>=1;assert(t.subrange(0,k)[0]==t[0]);}}
 assert(!rp::py_match_float(t)) by {if t.len()>=1 && t.last()=='\n' {let u=t.drop_last();assert(rp::unsigned(u)==u);if rp::float_text(u,true) {let k=choose|k:int| 0<k<rp::unsigned(u).len()-1 && #[trigger] rp::unsigned(u)[k]=='.' && rp::int_digits(rp::unsigned(u).subrange(0,k),true) && rp::digits(rp::unsigned(u).subrange(k+1,rp::unsigned(u).len() as int),true) && rp::unsigned(u).subrange(k+1,rp::unsigned(u).len() as int).len()>=1;assert(u.subrange(0,k)[0]==t[0]);}}}
}
/// A relationship JSON boolean orders as 1 or 0 (JSON_VALUE's spelling), while a node boolean never orders.
pub proof fn theorem_rel_bool_orders_as_number()
 requires cast_double(seq!['1'])==1real,
 ensures rel_where_ord(Json::Bool(true),Ord::Ge,1),!node_where_ord(nr::write(nr::Input::Bool(true)),Ord::Ge,1),
{}

// ---- string predicates (STARTS WITH) against a stored property (iteration 20) ----
pub open spec fn starts(x:Text,pre:Text)->bool {x.len()>=pre.len() && x.subrange(0,pre.len() as int)==pre}
/// Node: the stored value's text is tested, a stored number through its canonical text (observed natively).
pub open spec fn node_starts_with(s:nr::Stored,pre:Text)->bool {
 match s {nr::Stored::Text(x)=>starts(x,pre),nr::Stored::Number{payload,double}=>if double {starts(double_text(payload),pre)} else {starts(num_text(payload),pre)},nr::Stored::BigText(_)=>false}
}
/// A stored node integer satisfies a string prefix test on its digits, while RETURN reads it as an integer
/// (openCypher: a string predicate on a number is null).
pub proof fn theorem_node_number_matches_string_prefix()
 ensures node_starts_with(nr::Stored::Number{payload:12,double:false},seq!['1']),
  node_return(nr::Stored::Number{payload:12,double:false})==nr::Value::Integer(12),
{reveal_with_fuel(nat_text,2);assert(nat_text(12)=~=seq!['1','2']);assert(num_text(12).subrange(0,1)=~=seq!['1']);}
}
