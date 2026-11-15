use vstd::prelude::*;
verus! {
pub type Text=Seq<char>;
pub open spec fn ws(c:char)->bool {c==' ' || c=='\t' || c=='\n' || c=='\r'}
pub open spec fn digit(c:char)->bool {'0'<=c && c<='9'}
pub open spec fn value(c:char)->nat {match c{'0'=>0,'1'=>1,'2'=>2,'3'=>3,'4'=>4,'5'=>5,'6'=>6,'7'=>7,'8'=>8,'9'=>9,_=>0}}
pub enum Phase {Open,First,Next,Sign,Zero,Int,Dot,Frac,Exp,ExpSign,ExpDigits,After,End}
pub open spec fn complete(p:Phase)->bool {p is Zero || p is Int || p is Frac || p is ExpDigits}
pub open spec fn step(p:Phase,c:char)->Option<(Phase,bool)> {
    match p {
        Phase::Open=>if ws(c){Some((p,false))}else if c=='['{Some((Phase::First,false))}else{None},
        Phase::First|Phase::Next=>if ws(c){Some((p,false))}else if c==']' && p is First{Some((Phase::End,false))}
            else if c=='-'{Some((Phase::Sign,false))}else if c=='0'{Some((Phase::Zero,false))}else if digit(c){Some((Phase::Int,false))}else{None},
        Phase::Sign=>if c=='0'{Some((Phase::Zero,false))}else if digit(c){Some((Phase::Int,false))}else{None},
        Phase::Dot=>if digit(c){Some((Phase::Frac,false))}else{None},
        Phase::Exp=>if c=='+' || c=='-'{Some((Phase::ExpSign,false))}else if digit(c){Some((Phase::ExpDigits,false))}else{None},
        Phase::ExpSign=>if digit(c){Some((Phase::ExpDigits,false))}else{None},
        Phase::After=>if ws(c){Some((p,false))}else if c==','{Some((Phase::Next,false))}else if c==']'{Some((Phase::End,false))}else{None},
        Phase::End=>if ws(c){Some((p,false))}else{None},
        _=>{
            if digit(c) && !(p is Zero){Some((p,false))}
            else if c=='.' && (p is Int || p is Zero){Some((Phase::Dot,false))}
            else if (c=='e' || c=='E') && !(p is ExpDigits){Some((Phase::Exp,false))}
            else if ws(c){Some((Phase::After,true))}else if c==','{Some((Phase::Next,true))}else if c==']'{Some((Phase::End,true))}else{None}
        },
    }
}
pub open spec fn scan(t:Text,i:nat,p:Phase,n:nat)->Option<nat>
    decreases t.len()-i,
{
    if i>=t.len(){if p is End{Some(n)}else{None}}
    else{match step(p,t[i as int]){None=>None,Some((next,inc))=>scan(t,i+1,next,n+if inc{1nat}else{0nat})}}
}
pub open spec fn width(t:Text)->Option<nat> {scan(t,0,Phase::Open,0)}
pub open spec fn skip(t:Text,i:nat)->nat
    decreases t.len()-i,
{if i<t.len() && ws(t[i as int]){skip(t,i+1)}else{i}}
pub open spec fn literal(t:Text)->bool {let i=skip(t,0);i<t.len() && t[i as int]=='['}
pub open spec fn digits(t:Text,i:nat,n:nat)->Option<int>
    decreases t.len()-i,
{
    if i>=t.len(){Some(n as int)}else if digit(t[i as int]){digits(t,i+1,n*10+value(t[i as int]))}
    else{let j=skip(t,i);if j==t.len(){Some(n as int)}else{None}}
}
pub open spec fn integer(t:Text)->Option<int> {
    let i=skip(t,0);
    if i>=t.len(){None}else{
        let signed=t[i as int]=='-' || t[i as int]=='+';let j=if signed{i+1}else{i};
        if j>=t.len() || !digit(t[j as int]){None}else{
            let v=digits(t,j,0);if t[i as int]=='-'{match v{Some(x)=>Some(-x),None=>None}}else{v}}}
}
pub proof fn lemma_scan_width_bound(t:Text,i:nat,p:Phase,n:nat)
    requires i<=t.len(),
    ensures scan(t,i,p,n).is_some() ==> scan(t,i,p,n).unwrap()<=n+t.len()-i,
    decreases t.len()-i,
{
    if i<t.len(){match step(p,t[i as int]){Some((next,inc))=>{lemma_scan_width_bound(t,i+1,next,n+if inc{1nat}else{0nat});},_=>{}}}
}
pub proof fn theorem_raw_numeric_literals()
    ensures width(seq!['[',']'])==Some(0),width(seq!['[','1',',','2',',','3',']'])==Some(3),
        width(seq!['[','1',',','2',',','3',',','4',']'])==Some(4),
        width(seq!['[','1',',',']'])==None,width(seq!['[','.','1',']'])==None,
{
    reveal_with_fuel(scan,12);
}
pub proof fn theorem_raw_integer_carriers()
    ensures integer(seq!['4'])==Some(4),integer(seq![' ','+','4',' '])==Some(4),integer(seq!['-','3'])==Some(-3),integer(seq!['b','a','d'])==None,
{reveal_with_fuel(skip,4);reveal_with_fuel(digits,5);}
}
