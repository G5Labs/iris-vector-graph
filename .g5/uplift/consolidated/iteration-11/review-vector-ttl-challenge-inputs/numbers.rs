// Finite ASCII decimal producer. Binary64 conversion is a separate correspondence boundary.
use vstd::prelude::*;
use crate::{Text,Number};
verus! {
pub open spec fn power(n:nat)->nat decreases n,{if n==0{1}else{10*power((n-1) as nat)}}
pub open spec fn trim(t:Text)->Text {crate::json_width::trim(t)}
pub open spec fn exponent(t:Text,i:nat)->nat decreases t.len()-i,
{if i>=t.len() || t[i as int]=='e' || t[i as int]=='E'{i}else{exponent(t,i+1)}}
pub open spec fn fraction(t:Text,i:nat,n:nat,places:nat,dot:bool,digits:nat)->Option<(nat,nat)>
    decreases t.len()-i,
{
    if i>=t.len(){if digits>0{Some((n,places))}else{None}}
    else if crate::parser::digit(t[i as int]){fraction(t,i+1,n*10+crate::parser::value(t[i as int]),places+if dot{1nat}else{0nat},dot,digits+1)}
    else if t[i as int]=='.' && !dot{fraction(t,i+1,n,places,true,digits)}else{None}
}
pub open spec fn decimal(raw:Text)->Option<Number> {
    let t=trim(raw);if t.len()==0{None}else{let neg=t[0]=='-';let sign=neg || t[0]=='+';let i=if sign{1nat}else{0nat};let j=exponent(t,i);
        let exp=if j<t.len(){crate::parser::integer(t.subrange((j+1) as int,t.len() as int))}else{Some(0int)};
        if j<i || j>t.len() || exp.is_none(){None}else{match fraction(t.subrange(i as int,j as int),0,0,0,false,0){None=>None,Some((n,f))=>{
            let e=exp.unwrap()-(f as int);let signed=if neg{-(n as int)}else{n as int};Some(if e>=0{(signed*(power(e as nat) as int),1)}else{(signed,power((-e) as nat))})
        }}}
    }
}
pub open spec fn digit(n:nat)->char {if n==0{'0'}else if n==1{'1'}else if n==2{'2'}else if n==3{'3'}else if n==4{'4'}else if n==5{'5'}else if n==6{'6'}else if n==7{'7'}else if n==8{'8'}else{'9'}}
pub open spec fn natural(n:nat)->Text decreases n,
{if n<10{seq![digit(n)]}else{natural(n/10)+seq![digit(n%10)]}}
pub open spec fn integer(n:int)->Text {if n<0{seq!['-']+natural((-n) as nat)}else{natural(n as nat)}}
pub proof fn theorem_decimal_raw_typed_score()
    ensures decimal(seq!['0','.','7','5'])==Some((75,100)),decimal(seq!['1'])==Some((1,1)),decimal(seq!['b','a','d'])==None,
{assert(trim(seq!['1']) =~= seq!['1']);assert(exponent(seq!['1'],0)==1) by {reveal_with_fuel(exponent,2);};assert(fraction(seq!['1'],0,0,0,false,0)==Some((1,0))) by {reveal_with_fuel(fraction,2);};reveal_with_fuel(exponent,5);reveal_with_fuel(fraction,5);reveal_with_fuel(power,4);reveal_with_fuel(crate::json_width::start,5);reveal_with_fuel(crate::json_width::end,5);}
pub proof fn theorem_raw_integer_stringification()
    ensures integer(0)==seq!['0'],integer(-12)==seq!['-','1','2'],
{reveal_with_fuel(natural,3);}
}
