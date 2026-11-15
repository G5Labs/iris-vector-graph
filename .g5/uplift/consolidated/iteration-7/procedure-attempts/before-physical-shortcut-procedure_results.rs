// Handled db.labels projection. Label integers denote ordered single-character
// text values in the executable binding, not arbitrary SQL collation/Unicode.
use vstd::prelude::*;
use vstd::seq_lib::*;
verus! {
pub enum Value {Null, Bool(bool), Number(int), Text(int)}
pub enum Condition {All, Eq(Value), Ne(Value), IsNull, Unsupported, MissingParam}
pub enum Tail {None, With{input:Seq<char>,output:Seq<char>}, Match, Union, ReturnDistinct}
pub struct Label {pub graph:int,pub node:int,pub text:int}
pub struct Query {pub source:Seq<char>,pub alias:Seq<char>,pub condition:Condition,
    pub return_name:Option<Seq<char>>,pub order_name:Option<Seq<char>>,pub descending:bool,
    pub skip:nat,pub limit:Option<nat>,pub tail:Tail}
pub enum Outcome {Rows{column:Seq<char>,values:Seq<int>}, Refused}
pub open spec fn physical() -> Seq<char> {seq!['l','a','b','e','l']}
pub open spec fn eq(a:Value,b:Value) -> Option<bool> {
    match (a,b) {
        (Value::Null,_)|(_,Value::Null)=>None,
        (Value::Text(a),Value::Text(b))=>Some(a==b),
        (Value::Number(a),Value::Number(b))=>Some(a==b),
        (Value::Bool(a),Value::Bool(b))=>Some(a==b),
        _=>Some(false),
    }
}
pub open spec fn negate(v:Option<bool>) -> Option<bool> {if v.is_none(){None}else{Some(!v.unwrap())}}
pub open spec fn passes(l:int,c:Condition) -> bool {
    match c {Condition::All=>true,Condition::Eq(v)=>eq(Value::Text(l),v)==Some(true),
        Condition::Ne(v)=>negate(eq(Value::Text(l),v))==Some(true),Condition::IsNull=>false,
        _=>false}
}
pub open spec fn texts(records:Seq<Label>) -> Seq<int> {records.map_values(|r:Label|r.text)}
pub open spec fn leq() -> spec_fn(int,int)->bool {|a:int,b:int|a<=b}
pub open spec fn provider(records:Seq<Label>,requested_graph:int) -> Seq<int> {
    texts(records).to_set().to_seq().sort_by(leq())
}
pub open spec fn filtered(rows:Seq<int>,c:Condition) -> Seq<int> {rows.filter(|l:int|passes(l,c))}
pub open spec fn cut(rows:Seq<int>,skip:nat,limit:Option<nat>) -> Seq<int> {
    let start=if skip<rows.len(){skip as int}else{rows.len() as int};
    let rest=rows.subrange(start,rows.len() as int);
    if limit.is_some() && limit.unwrap()<rest.len(){rest.take(limit.unwrap() as int)}else{rest}
}
pub open spec fn bad_tail(t:Tail,alias:Seq<char>) -> bool {
    match t {Tail::None=>false,Tail::With{input,output}=>input!=alias || output!=input,_=>true}
}
pub open spec fn consume(rows:Seq<int>,q:Query) -> Outcome {
    if bad_tail(q.tail,q.alias) || (q.return_name.is_some() && q.return_name.unwrap()!=q.alias) {
        Outcome::Refused
    } else if rows.len()>0 && !matches!(q.condition,Condition::All)
        && (q.source!=physical() || matches!(q.condition,Condition::Unsupported|Condition::MissingParam)) {
        Outcome::Refused
    } else {
        let selected=filtered(rows,q.condition);
        if q.return_name.is_some() && q.source!=physical() && selected.len()>0 {Outcome::Refused}
        else {
            let column=if q.return_name.is_some(){q.return_name.unwrap()}else{physical()};
            if q.order_name.is_some() && q.order_name.unwrap()!=column {Outcome::Refused}
            else {let ordered=if q.order_name.is_some() && q.descending{selected.reverse()}else{selected};
                Outcome::Rows{column,values:cut(ordered,q.skip,q.limit)}}
        }
    }
}
pub open spec fn call(records:Seq<Label>,graph:int,q:Query) -> Outcome {consume(provider(records,graph),q)}
pub open spec fn simple(alias:Seq<char>,c:Condition,ret:bool) -> Query {
    Query{source:physical(),alias,condition:c,return_name:if ret{Some(alias)}else{None},
        order_name:None,descending:false,skip:0,limit:None,tail:Tail::None}
}
pub proof fn theorem_graph_is_ignored(s:Seq<Label>,g:int,h:int,q:Query)
    ensures call(s,g,q)==call(s,h,q),
{}
pub proof fn theorem_complete_provider(s:Seq<Label>,g:int,l:int)
    ensures provider(s,g).contains(l) <==> (exists|i:int|0<=i<s.len() && s[i].text==l),
{
    let mapped=texts(s);let keys=mapped.to_set();
    keys.to_seq().lemma_sort_by_ensures(leq());
    keys.lemma_to_seq_to_set_id();
    assert(keys.to_seq().to_set()==keys);
    mapped.to_set_ensures();keys.to_seq().to_set_ensures();
    if mapped.contains(l) {let i=choose|i:int|0<=i<mapped.len() && mapped[i]==l;assert(s[i].text==l);}
    if exists|i:int|0<=i<s.len() && s[i].text==l {let i=choose|i:int|0<=i<s.len() && s[i].text==l;assert(mapped[i]==l);}
    assert(keys.to_seq().to_set().contains(l)==keys.contains(l));
    assert(keys.to_seq().contains(l)==keys.to_seq().to_set().contains(l));
    assert(mapped.contains(l)==keys.contains(l));
    keys.to_seq().to_multiset_ensures();provider(s,g).to_multiset_ensures();
    assert(keys.to_seq().to_multiset()==provider(s,g).to_multiset());
    to_multiset_contains(keys.to_seq(),l);to_multiset_contains(provider(s,g),l);
    assert(provider(s,g).contains(l)==mapped.contains(l));
    assert(mapped.contains(l) <==> (exists|i:int|0<=i<s.len() && s[i].text==l));
}
pub proof fn theorem_distinct_provider(s:Seq<Label>,g:int)
    ensures provider(s,g).no_duplicates(),
{let keys=texts(s).to_set();keys.lemma_to_seq_no_duplicates();
 keys.to_seq().lemma_sort_by_ensures(leq());keys.to_seq().lemma_multiset_has_no_duplicates();
 provider(s,g).lemma_multiset_has_no_duplicates_conv();}
pub proof fn theorem_only_true_passes(l:int,v:Value)
    ensures passes(l,Condition::Eq(v)) <==> eq(Value::Text(l),v)==Some(true),
        !passes(l,Condition::Eq(Value::Null)),!passes(l,Condition::Ne(Value::Null)),
        !passes(l,Condition::Eq(Value::Bool(true))),
{}
pub proof fn lemma_all(rows:Seq<int>)
    ensures filtered(rows,Condition::All)==rows,
    decreases rows.len(),
{reveal(Seq::filter);if rows.len()>0{lemma_all(rows.drop_last());assert(rows.drop_last().push(rows.last())=~=rows);}}
pub proof fn lemma_uncut(rows:Seq<int>)
    ensures cut(rows,0,None)==rows,
{assert(rows.subrange(0,rows.len() as int)=~=rows);}
pub proof fn theorem_alias_return(rows:Seq<int>,alias:Seq<char>)
    ensures consume(rows,simple(alias,Condition::All,true))==(Outcome::Rows{column:alias,values:rows}),
{lemma_all(rows);lemma_uncut(rows);lemma_uncut(seq![]);reveal(Seq::filter);}
pub proof fn theorem_bare_alias_keeps_physical(rows:Seq<int>,alias:Seq<char>)
    ensures consume(rows,simple(alias,Condition::All,false))==(Outcome::Rows{column:physical(),values:rows}),
{lemma_all(rows);lemma_uncut(rows);lemma_uncut(seq![]);reveal(Seq::filter);}
pub proof fn theorem_unsupported_nonempty_refused(rows:Seq<int>,alias:Seq<char>)
    requires rows.len()>0,
    ensures consume(rows,simple(alias,Condition::Unsupported,true))==Outcome::Refused,
{}
pub proof fn theorem_empty_skips_expression_validation(alias:Seq<char>)
    ensures consume(seq![],simple(alias,Condition::Unsupported,true))==(Outcome::Rows{column:alias,values:seq![]}),
        consume(seq![],simple(alias,Condition::MissingParam,true))==(Outcome::Rows{column:alias,values:seq![]}),
{reveal(Seq::filter);lemma_uncut(seq![]);}
pub proof fn theorem_unsupported_clause_always_refused(rows:Seq<int>,q:Query)
    ensures consume(rows,Query{tail:Tail::Match,..q})==Outcome::Refused,
        consume(rows,Query{tail:Tail::Union,..q})==Outcome::Refused,
        consume(rows,Query{tail:Tail::ReturnDistinct,..q})==Outcome::Refused,
{}
pub proof fn theorem_order_requires_result_column(rows:Seq<int>,alias:Seq<char>)
    requires alias!=physical(),
    ensures consume(rows,Query{order_name:Some(alias),..simple(alias,Condition::All,false)})==Outcome::Refused,
        consume(rows,Query{order_name:Some(alias),..simple(alias,Condition::All,true)})==(Outcome::Rows{column:alias,values:rows}),
{lemma_all(rows);lemma_uncut(rows);lemma_uncut(seq![]);reveal(Seq::filter);}
pub proof fn theorem_wrong_source_empty_vs_nonempty(alias:Seq<char>,src:Seq<char>,rows:Seq<int>)
    requires src!=physical(),rows.len()>0,
    ensures consume(rows,Query{source:src,..simple(alias,Condition::All,true)})==Outcome::Refused,
        consume(seq![],Query{source:src,..simple(alias,Condition::All,true)})==(Outcome::Rows{column:alias,values:seq![]}),
{lemma_all(rows);lemma_uncut(rows);lemma_uncut(seq![]);reveal(Seq::filter);}
pub proof fn theorem_filter_before_limit(rows:Seq<int>,alias:Seq<char>,wanted:int)
    ensures consume(rows,Query{limit:Some(1),..simple(alias,Condition::Eq(Value::Text(wanted)),true)})
        ==(Outcome::Rows{column:alias,values:cut(filtered(rows,Condition::Eq(Value::Text(wanted))),0,Some(1))}),
{}
pub proof fn theorem_final_filter_sound(rows:Seq<int>,alias:Seq<char>,wanted:int)
    ensures forall|i:int|0<=i<filtered(rows,Condition::Eq(Value::Text(wanted))).len()
        ==> filtered(rows,Condition::Eq(Value::Text(wanted)))[i]==wanted,
{
    assert forall|i:int|0<=i<filtered(rows,Condition::Eq(Value::Text(wanted))).len()
        implies filtered(rows,Condition::Eq(Value::Text(wanted)))[i]==wanted by {
        rows.lemma_filter_pred(|l:int|passes(l,Condition::Eq(Value::Text(wanted))),i);
    }
}
pub proof fn theorem_with_scope_and_alias(rows:Seq<int>,a:Seq<char>,b:Seq<char>)
    requires a!=b,
    ensures consume(rows,Query{tail:Tail::With{input:a,output:b},..simple(a,Condition::All,true)})==Outcome::Refused,
        consume(rows,Query{tail:Tail::With{input:a,output:a},..simple(a,Condition::All,true)})==(Outcome::Rows{column:a,values:rows}),
{lemma_all(rows);lemma_uncut(rows);}
pub proof fn theorem_zero_limit_empty(rows:Seq<int>)
    ensures cut(rows,0,Some(0))==seq![],cut(rows,rows.len(),None)==seq![],
{}
pub proof fn theorem_producer_to_public_alias(s:Seq<Label>,graph:int,alias:Seq<char>)
    ensures call(s,graph,simple(alias,Condition::All,true))==(Outcome::Rows{column:alias,values:provider(s,graph)}),
{theorem_alias_return(provider(s,graph),alias);}
}
