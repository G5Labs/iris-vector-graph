// product 3eaa79cf: the type rank of Graph.KG.Cypher.SortKey.Key / Graph_KG.CY_SORT_KEY (ORDER BY) for ordinary scalar
// values, and its disagreement with node WHERE ordering (typed_equality). iris_src/src/Graph/KG/Cypher/SortKey.cls:9-153.
use vstd::prelude::*;
#[path="../typed_equality/typed_equality.rs"] pub mod te;
verus! {
use te::nr;
pub type Text=Seq<char>;
/// The type argument: "x" an untyped stored value (ORDER BY passes 'x'), or a JSON value's type.
pub enum Ty {X,Str,Bool,Num,Null}
/// Provider: ObjectScript $IsValidNum. Uninterpreted; observed in the binding.
pub uninterp spec fn is_valid_num(v:Text)->bool;
pub open spec fn digit(c:char)->bool {'0'<=c<='9'}
/// The ordinary scalar text this model covers: not a list/map/graph JSON, not a duration ('P...'), not a date or time.
pub open spec fn scalar_text(v:Text)->bool {
 v.len()>0 && v[0]!='[' && v[0]!='{' && v[0]!='P'
 && !(v.len()>=10 && v[4]=='-' && v[7]=='-')
 && !(v.len()>=5 && digit(v[0]) && digit(v[1]) && digit(v[3]) && digit(v[4]))
}
pub open spec fn tru()->Text {seq!['t','r','u','e']}
pub open spec fn fals()->Text {seq!['f','a','l','s','e']}
pub open spec fn nan()->Text {seq!['N','a','N']}
/// The key's first character, in Key's branch order. `None` is SQL NULL (v = ""); an empty string reaches the key as
/// $Char(0) and ranks as a string. Stored $DOUBLE NaN/INF are outside this scalar domain.
pub open spec fn rank(v:Option<Text>,t:Ty)->char {
 match v {
  None=>'z',
  Some(s)=>if t==Ty::Null {'z'} else if s.len()==0 {'l'}
   else if t==Ty::Str {'l'} else if t==Ty::Bool {'m'}
   else if t==Ty::X && (s==tru() || s==fals()) {'m'} else if t==Ty::X && s==nan() {'o'}
   else if (t==Ty::Num) || (t==Ty::X && is_valid_num(s)) {'n'} else {'l'},
 }
}

/// openCypher orderability of the scalar kinds: strings < booleans < numbers < NaN < null (key prefixes compare as text).
pub proof fn theorem_rank_order() ensures 'l'<'m','m'<'n','n'<'o','o'<'z' {}
/// ORDER BY sorts an untyped stored text that $IsValidNum accepts among the numbers.
pub proof fn theorem_untyped_numeric_text_sorts_as_number(v:Text)
 requires scalar_text(v),is_valid_num(v),v!=tru(),v!=fals(),v!=nan(),
 ensures rank(Some(v),Ty::X)=='n',
{}
/// A value typed as a string ranks as a string whatever it spells.
pub proof fn theorem_typed_string_sorts_as_string(v:Text) ensures rank(Some(v),Ty::Str)=='l' {}
/// Untyped text that is not a number, boolean or NaN ranks as a string.
pub proof fn theorem_word_sorts_as_string(v:Text)
 requires scalar_text(v),!is_valid_num(v),v!=tru(),v!=fals(),v!=nan(),
 ensures rank(Some(v),Ty::X)=='l',
{}
/// An empty string (bound as $Char(0)) sorts first among the strings, not as null.
pub proof fn theorem_empty_string_sorts_as_string(t:Ty) requires t!=Ty::Null ensures rank(Some(Seq::<char>::empty()),t)=='l' {}
/// A missing property sorts last ascending.
pub proof fn theorem_null_sorts_last(t:Ty) ensures rank(None,t)=='z' {}
/// A stored boolean text sorts before every untyped numeric text.
pub proof fn theorem_bool_before_number(v:Text)
 requires scalar_text(v),is_valid_num(v),v!=tru(),v!=fals(),v!=nan(),
 ensures rank(Some(tru()),Ty::X)<rank(Some(v),Ty::X),
{}
/// Node: WHERE drops a numeric-looking text against any number, while ORDER BY sorts it among the numbers.
pub proof fn theorem_node_where_and_order_by_disagree(v:Text,o:te::Ord,m:int)
 requires scalar_text(v),is_valid_num(v),v!=tru(),v!=fals(),v!=nan(),
 ensures !te::node_where_ord(nr::Stored::Text(v),o,m),rank(Some(v),Ty::X)=='n',
{te::theorem_node_text_never_orders(v,o,m);}

// ---- the two executors' argument to the key (provider premises, observed natively) ----
/// SQL path: CY_SORT_KEY receives a stored empty string as $Char(0), modeled as the empty text.
pub open spec fn sql_arg(s:Text)->Option<Text> {Some(s)}
/// Native executor: Exec.SortKey passes the stored value to SortKey.Key as ObjectScript "", which is its null.
pub open spec fn native_arg(s:Text)->Option<Text> {if s.len()==0 {None} else {Some(s)}}
/// The SQL path sorts an empty string before every number; the native executor sorts it after every number, with the
/// nulls. Equal answers (query.native.equal-answers) therefore fail for ORDER BY over an empty-string property.
pub proof fn theorem_executors_disagree_on_empty_string(v:Text)
 requires scalar_text(v),is_valid_num(v),v!=tru(),v!=fals(),v!=nan(),
 ensures rank(sql_arg(Seq::<char>::empty()),Ty::X)<rank(sql_arg(v),Ty::X),
  rank(native_arg(v),Ty::X)<rank(native_arg(Seq::<char>::empty()),Ty::X),
{assert(v.len()>0);}
}
