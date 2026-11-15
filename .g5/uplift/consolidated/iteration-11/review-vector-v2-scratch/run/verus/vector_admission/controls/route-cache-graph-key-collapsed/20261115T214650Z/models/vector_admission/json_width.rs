// Raw-character JSON syntax and outer-array count. No supplied parser result.
use vstd::prelude::*;
use crate::parser::{Text,Phase};
verus! {
pub enum Ctx {First(nat),Next(nat),After(nat),ObjFirst,ObjNext,Colon,ObjValue,ObjAfter}
pub enum Lex {Normal,String{key:bool,escape:bool,unicode:nat},Number(Phase),Word(Text)}
pub struct State {pub stack:Seq<Ctx>,pub lex:Lex,pub done:bool,pub width:Option<nat>}
pub open spec fn initial()->State {State{stack:seq![],lex:Lex::Normal,done:false,width:None}}
pub open spec fn strip_ws(c:char)->bool {
    ('\u{9}'<=c && c<='\u{d}') || ('\u{1c}'<=c && c<=' ') || c=='\u{85}' || c=='\u{a0}' || c=='\u{1680}'
    || ('\u{2000}'<=c && c<='\u{200a}') || c=='\u{2028}' || c=='\u{2029}' || c=='\u{202f}' || c=='\u{205f}' || c=='\u{3000}'
}
pub open spec fn start(t:Text,i:nat)->nat decreases t.len()-i,
{if i<t.len() && strip_ws(t[i as int]){start(t,i+1)}else{i}}
pub open spec fn end(t:Text,n:nat)->nat recommends n<=t.len(), decreases n,
{if n>0 && strip_ws(t[(n-1) as int]){end(t,(n-1) as nat)}else{n}}
pub open spec fn trim(t:Text)->Text {let a=start(t,0);let b=end(t,t.len());if a>=b{seq![]}else{t.subrange(a as int,b as int)}}
pub open spec fn literal(t:Text)->bool {let a=start(t,0);a<t.len() && t[a as int]=='['}
pub open spec fn hex(c:char)->bool {crate::parser::digit(c) || ('a'<=c && c<='f') || ('A'<=c && c<='F')}
pub open spec fn finish(s:State,w:Option<nat>)->Option<State> {
    if s.stack.len()==0{Some(State{lex:Lex::Normal,done:true,width:w,..s})}
    else{let i=s.stack.len()-1;match s.stack.last(){
        Ctx::First(n)|Ctx::Next(n)=>Some(State{lex:Lex::Normal,stack:s.stack.update(i as int,Ctx::After(n+1)),..s}),
        Ctx::ObjValue=>Some(State{lex:Lex::Normal,stack:s.stack.update(i as int,Ctx::ObjAfter),..s}),_=>None}}
}
pub open spec fn close(s:State,w:Option<nat>)->Option<State> {
    if s.stack.len()==0{None}else{finish(State{stack:s.stack.drop_last(),..s},w)}
}
pub open spec fn begin(s:State,c:char)->Option<State> {
    if c=='['{Some(State{stack:s.stack.push(Ctx::First(0)),..s})}
    else if c=='{'{Some(State{stack:s.stack.push(Ctx::ObjFirst),..s})}
    else if c=='"'{Some(State{lex:Lex::String{key:false,escape:false,unicode:0},..s})}
    else if c=='-'{Some(State{lex:Lex::Number(Phase::Sign),..s})}
    else if c=='0'{Some(State{lex:Lex::Number(Phase::Zero),..s})}
    else if crate::parser::digit(c){Some(State{lex:Lex::Number(Phase::Int),..s})}
    else if c=='t'{Some(State{lex:Lex::Word(seq!['r','u','e']),..s})}
    else if c=='f'{Some(State{lex:Lex::Word(seq!['a','l','s','e']),..s})}
    else if c=='n'{Some(State{lex:Lex::Word(seq!['u','l','l']),..s})}
    else if c=='N'{Some(State{lex:Lex::Word(seq!['a','N']),..s})}
    else if c=='I'{Some(State{lex:Lex::Word(seq!['n','f','i','n','i','t','y']),..s})}
    else{None}
}
pub open spec fn normal(s:State,c:char)->Option<State> {
    if crate::parser::ws(c){Some(s)}else if s.done{None}
    else if s.stack.len()==0{begin(s,c)}else{let i=s.stack.len()-1;match s.stack.last(){
        Ctx::First(n)=>if c==']'{close(s,Some(n))}else{begin(s,c)},
        Ctx::Next(_)=>begin(s,c),
        Ctx::After(n)=>if c==','{Some(State{stack:s.stack.update(i as int,Ctx::Next(n)),..s})}else if c==']'{close(s,Some(n))}else{None},
        Ctx::ObjFirst|Ctx::ObjNext=>if c=='"'{Some(State{lex:Lex::String{key:true,escape:false,unicode:0},..s})}
            else if c=='}' && s.stack.last() is ObjFirst{close(s,None)}else{None},
        Ctx::Colon=>if c==':'{Some(State{stack:s.stack.update(i as int,Ctx::ObjValue),..s})}else{None},
        Ctx::ObjValue=>begin(s,c),
        Ctx::ObjAfter=>if c==','{Some(State{stack:s.stack.update(i as int,Ctx::ObjNext),..s})}else if c=='}'{close(s,None)}else{None},
    }}
}
pub open spec fn step(s:State,c:char)->Option<State> {
    match s.lex {
        Lex::Normal=>normal(s,c),
        Lex::Word(rest)=>if rest.len()==0 || c!=rest[0]{None}else if rest.len()==1{finish(State{lex:Lex::Normal,..s},None)}
            else{Some(State{lex:Lex::Word(rest.drop_first()),..s})},
        Lex::String{key,escape,unicode}=>{
            if unicode>0{if hex(c){Some(State{lex:Lex::String{key,escape:false,unicode:(unicode-1) as nat},..s})}else{None}}
            else if escape{
                if c=='u'{Some(State{lex:Lex::String{key,escape:false,unicode:4},..s})}
                else if c=='"' || c=='\\' || c=='/' || c=='b' || c=='f' || c=='n' || c=='r' || c=='t'{Some(State{lex:Lex::String{key,escape:false,unicode:0},..s})}
                else{None}
            }else if c=='\\'{Some(State{lex:Lex::String{key,escape:true,unicode:0},..s})}
            else if c=='"'{
                if key{if s.stack.len()==0{None}else{Some(State{lex:Lex::Normal,stack:s.stack.update((s.stack.len()-1) as int,Ctx::Colon),..s})}}
                else{finish(State{lex:Lex::Normal,..s},None)}
            }else if c<' '{None}else{Some(s)}
        },
        Lex::Number(p)=>{
            if crate::parser::complete(p) && (crate::parser::ws(c) || c==',' || c==']' || c=='}'){
                match finish(State{lex:Lex::Normal,..s},None){Some(next)=>normal(next,c),None=>None}
            }else if p is Sign && c=='I'{Some(State{lex:Lex::Word(seq!['n','f','i','n','i','t','y']),..s})}
            else{match crate::parser::step(p,c){Some((next,false))=>Some(State{lex:Lex::Number(next),..s}),_=>None}}
        },
    }
}
pub open spec fn scan(t:Text,i:nat,s:State)->Option<State>
    decreases t.len()-i,
{if i>=t.len(){Some(s)}else{match step(s,t[i as int]){Some(next)=>scan(t,i+1,next),None=>None}}}
pub open spec fn parsed(t:Text)->Option<Option<nat>> {
    match scan(t,0,initial()){
        None=>None,
        Some(s)=>if s.done{Some(s.width)}else{match s.lex{Lex::Number(p)=>if s.stack.len()==0 && crate::parser::complete(p){Some(None)}else{None},_=>None}},
    }
}
pub open spec fn width(t:Text)->Option<nat> {match parsed(trim(t)){Some(w)=>w,None=>None}}
pub proof fn theorem_nested_and_typed_outer_width()
    ensures width(seq!['[','[','1',',','2',']',',','{','"','k','"',':','t','r','u','e','}',']'])==Some(2),
        width(seq!['[','t','r','u','e',',','f','a','l','s','e',',','n','u','l','l',',','"','x','"',']'])==Some(4),
{
    reveal_with_fuel(scan,32);reveal_with_fuel(start,32);reveal_with_fuel(end,32);
}
pub proof fn theorem_escaped_comma_and_empty()
    ensures width(seq!['[','"','a',',','b','"',',','"','\\','"','"',']'])==Some(2),width(seq![' ', '[',']',' '])==Some(0),
        width(seq!['[','1',',',']'])==None,
{reveal_with_fuel(scan,24);reveal_with_fuel(start,24);reveal_with_fuel(end,24);}
pub proof fn lemma_scan_suffix(t:Text,u:Text,j:nat,s:State)
    requires j<=u.len(),
    ensures scan(t+u,t.len()+j,s)==scan(u,j,s),
    decreases u.len()-j,
{
    if j<u.len(){match step(s,u[j as int]){Some(next)=>lemma_scan_suffix(t,u,j+1,next),_=>{}}}
}
pub proof fn lemma_scan_concat(t:Text,u:Text,i:nat,s:State)
    requires i<=t.len(),
    ensures scan(t+u,i,s)==match scan(t,i,s){Some(mid)=>scan(u,0,mid),None=>None},
    decreases t.len()-i,
{
    if i==t.len(){lemma_scan_suffix(t,u,0,s);}
    else{match step(s,t[i as int]){Some(next)=>lemma_scan_concat(t,u,i+1,next),_=>{}}}
}
pub proof fn lemma_word_scan(word:Text,s:State)
    requires word.len()>0,s.lex==Lex::Word(word),
    ensures scan(word,0,s)==finish(State{lex:Lex::Normal,..s},None),
    decreases word.len(),
{
    if word.len()>1{
        let tail=word.drop_first();let next=State{lex:Lex::Word(tail),..s};
        assert(step(s,word[0])==Some(next));lemma_word_scan(tail,next);
        assert(word =~= seq![word[0]]+tail);lemma_scan_suffix(seq![word[0]],tail,0,next);
    }else{reveal_with_fuel(scan,2);}
}
pub proof fn theorem_python_nonfinite_extensions()
    ensures width(seq!['[','N','a','N',']'])==Some(1),
{
    reveal_with_fuel(scan,8);reveal_with_fuel(start,8);reveal_with_fuel(end,8);
}
pub proof fn theorem_numeric_outer_counts()
    ensures width(seq!['[','1',',','2',',','3',']'])==Some(3),width(seq!['[','1',',','2',',','3',',','4',']'])==Some(4),
{reveal_with_fuel(scan,12);reveal_with_fuel(start,12);reveal_with_fuel(end,12);}

}
