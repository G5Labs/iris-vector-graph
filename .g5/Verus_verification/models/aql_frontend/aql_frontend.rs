// Ordinary correctness only: numeric lexer domain -> depth AST -> Cypher bounds,
// literal/null normalization -> null operator. No query execution or SQL proof.
use vstd::prelude::*;
verus! {
pub enum Token {Int(nat),Float(nat)}
// n is the already scanned nonempty digit prefix; inspect the actual next two
// characters. Integer digit accumulation and overflow are outside this slice.
pub open spec fn decimal(t:Seq<char>) -> bool {
    t.len()>0 && t[0]=='.' && (t.len()<2 || t[1]!='.')
}
pub open spec fn lex(n:nat,t:Seq<char>) -> Token {if decimal(t){Token::Float(n)}else{Token::Int(n)}}
pub open spec fn depth(a:Token,b:Option<Token>) -> Option<(nat,nat)> {
    match a {Token::Int(n)=>match b {None=>Some((n,n)),Some(Token::Int(m))=>Some((n,m)),_=>None},_=>None}
}
pub enum Expr {Null,TextNull,Value(int)}
pub enum Operator {Eq,Ne,Lt}
pub enum Predicate {IsNull,IsNotNull,Compare(Operator,Expr)}
pub open spec fn resolve(op:Operator,right:Expr) -> Predicate {
    match (op,right) {(Operator::Eq,Expr::Null)=>Predicate::IsNull,
        (Operator::Ne,Expr::Null)=>Predicate::IsNotNull,_=>Predicate::Compare(op,right)}
}
pub open spec fn hops(a:Token,b:Option<Token>) -> Option<(nat,nat)> {depth(a,b)}
pub proof fn theorem_range_preserves_both_bounds(n:nat,m:nat)
    ensures hops(lex(n,seq!['.','.']),Some(lex(m,seq![])))==Some((n,m)),
{}
pub proof fn theorem_decimal_depth_refused(n:nat,m:nat)
    ensures depth(lex(n,seq!['.','5']),None)==None,depth(lex(n,seq![]),Some(lex(m,seq!['.'])))==None,
{}
pub proof fn theorem_single_depth_keeps_both(n:nat)
    ensures hops(lex(n,seq![]),None)==Some((n,n)),
{}
pub proof fn theorem_null_operators()
    ensures resolve(Operator::Eq,Expr::Null)==Predicate::IsNull,
        resolve(Operator::Ne,Expr::Null)==Predicate::IsNotNull,
{}
pub proof fn theorem_string_null_is_value()
    ensures resolve(Operator::Eq,Expr::TextNull)==Predicate::Compare(Operator::Eq,Expr::TextNull),
{}
pub proof fn theorem_non_equality_null_stays_compare()
    ensures resolve(Operator::Lt,Expr::Null)==Predicate::Compare(Operator::Lt,Expr::Null),
{}
}
