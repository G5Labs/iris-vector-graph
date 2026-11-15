use vstd::prelude::*;
use crate::{Raw,Text};
verus! {
pub struct Catalog {pub compiled:Raw<Seq<Text>>,pub lower:Raw<Seq<Option<Text>>>,pub upper:Raw<Seq<Option<Text>>>}
pub enum Found {Miss,Bad,Value(int)}
pub open spec fn comma_end(t:Text,i:nat)->nat decreases t.len()-i,
{if i<t.len() && t[i as int]!=','{comma_end(t,i+1)}else{i}}
pub open spec fn digit_end(t:Text,i:nat)->nat decreases t.len()-i,
{if i<t.len() && crate::parser::digit(t[i as int]){digit_end(t,i+1)}else{i}}
pub open spec fn control_end(t:Text,i:nat)->nat decreases t.len()-i,
{if i<t.len() && t[i as int]<='\u{1f}'{control_end(t,i+1)}else{i}}
pub open spec fn len_token(t:Text,i:nat)->Option<nat> decreases t.len()-i,
{
    if i+4>t.len(){None}else if (i==0 || t[(i-1) as int]==',') && t.subrange(i as int,(i+4) as int)==seq!['L','E','N',',']{Some(i+4)}
    else{len_token(t,i+1)}
}
pub open spec fn control_len(t:Text,i:nat)->Option<int> decreases t.len()-i,
{
    if i+3>=t.len(){None}else{
        let j=control_end(t,i+3);let k=digit_end(t,j);
        if t.subrange(i as int,(i+3) as int)==seq!['L','E','N'] && j>i+3 && k>j && k<=t.len(){crate::parser::integer(t.subrange(j as int,k as int))}
        else{control_len(t,i+1)}}
}
pub open spec fn compiled_one(t:Text)->Found {
    match len_token(t,0){Some(i)=>{let j=comma_end(t,i);if j<i || j>t.len(){Found::Bad}else{match crate::parser::integer(t.subrange(i as int,j as int)){Some(n)=>Found::Value(n),None=>Found::Bad}}},
        None=>match control_len(t,0){Some(n)=>Found::Value(n),None=>Found::Miss}}
}
pub open spec fn compiled(rows:Seq<Text>)->Found decreases rows.len(),
{if rows.len()==0{Found::Miss}else{match compiled_one(rows[0]){Found::Miss=>compiled(rows.drop_first()),other=>other}}}
pub open spec fn close_digits(t:Text,i:nat,best:Option<int>)->Option<int> decreases t.len()-i,
{
    if i>=t.len(){best}else{
        let j=digit_end(t,i);let k=crate::parser::skip(t,j);
        let next=if crate::parser::digit(t[i as int]) && (i==0 || !crate::parser::digit(t[(i-1) as int])) && k<t.len() && t[k as int]==')' && j<=t.len(){crate::parser::integer(t.subrange(i as int,j as int))}else{best};
        close_digits(t,i+1,next)}
}
pub open spec fn info_one(t:Text)->Option<int> {
    let n=close_digits(t,0,None);if n.is_some(){n}else{let ds=t.filter(|c:char|crate::parser::digit(c));crate::parser::integer(ds)}
}
pub open spec fn info(row:Seq<Option<Text>>)->Option<int> decreases row.len(),
{if row.len()==0{None}else{match row[0]{Some(t)=>if t.len()==0{info(row.drop_first())}else{match info_one(t){Some(n)=>Some(n),None=>info(row.drop_first())}},None=>info(row.drop_first())}}}
pub open spec fn fallback(c:Catalog)->(Option<int>,nat) {
    match c.lower{
        Raw::Error(_)=>(None,3),
        Raw::Rows(row)=>if row.len()>0{(info(row),3)}else{match c.upper{Raw::Error(_)=>(None,4),Raw::Rows(row)=>(info(row),4)}},
    }
}
pub open spec fn raw(c:Catalog)->(Option<int>,nat) {
    match c.compiled{Raw::Rows(rows)=>match compiled(rows){Found::Value(n)=>(Some(n),2),_=>fallback(c)},Raw::Error(_)=>fallback(c)}
}
pub open spec fn read(c:Catalog)->(Option<int>,nat) {
    let out=raw(c);(match out.0{Some(n)=>if n==0{None}else{Some(n)},None=>None},out.1)
}
pub proof fn theorem_compiled_raw_width()
    ensures compiled_one(seq!['L','E','N',',','4'])==Found::Value(4),
        compiled_one(seq!['L','E','N','\u{1}','\u{3}','4'])==Found::Value(4),
        compiled_one(seq!['L','E','N',',','b','a','d']) is Bad,
{
    crate::parser::theorem_raw_integer_carriers();
    reveal_with_fuel(len_token,3);
    let a=seq!['L','E','N',',','4'];assert(a.subrange(0,4) =~= seq!['L','E','N',',']);assert(len_token(a,0)==Some(4));assert(comma_end(a,4)==5) by {reveal_with_fuel(comma_end,2);}
    assert(a.subrange(4,5) =~= seq!['4']);assert(compiled_one(a)==Found::Value(4));
    let b=seq!['L','E','N','\u{1}','\u{3}','4'];assert(len_token(b,0)==None) by {reveal_with_fuel(len_token,4);}
    assert(control_end(b,3)==5) by {reveal_with_fuel(control_end,3);}
    assert(digit_end(b,5)==6) by {reveal_with_fuel(digit_end,2);}
    assert(b.subrange(0,3) =~= seq!['L','E','N']);assert(b.subrange(5,6) =~= seq!['4']);reveal_with_fuel(control_len,1);assert(control_len(b,0)==Some(4));assert(compiled_one(b)==Found::Value(4));
    let bad=seq!['L','E','N',',','b','a','d'];assert(bad.subrange(0,4) =~= seq!['L','E','N',',']);assert(len_token(bad,0)==Some(4));assert(comma_end(bad,4)==7) by {reveal_with_fuel(comma_end,4);}
    assert(bad.subrange(4,7) =~= seq!['b','a','d']);assert(compiled_one(bad) is Bad);
}
pub proof fn theorem_info_raw_width_and_heuristic()
    ensures info_one(seq!['V','E','C','T','O','R','(','D','O','U','B','L','E',',','4',')'])==Some(4),
        info_one(seq!['V','A','R','C','H','A','R','(','4','0','0','0',')'])==Some(4000),
{
    reveal_with_fuel(close_digits,20);reveal_with_fuel(digit_end,20);reveal_with_fuel(crate::parser::skip,20);reveal_with_fuel(crate::parser::digits,20);
}
}
