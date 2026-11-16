// Source ORDER BY abstraction: derive an ordered enumeration from raw rows, never accept selected IDs.
use vstd::prelude::*;
verus! {
pub open spec fn insert<T>(s:Seq<T>,x:T,k:spec_fn(T)->int)->Seq<T> decreases s.len(){if s.len()==0{seq![x]}else if k(x)<=k(s[0]){seq![x]+s}else{seq![s[0]]+insert(s.drop_first(),x,k)}}
pub open spec fn sort<T>(s:Seq<T>,k:spec_fn(T)->int)->Seq<T> decreases s.len(){if s.len()==0{s}else{insert(sort(s.drop_last(),k),s.last(),k)}}
pub open spec fn below<T>(h:T,s:Seq<T>,k:spec_fn(T)->int)->bool{forall|i:int|0<=i<s.len()==>k(h)<=k(#[trigger] s[i])}
pub open spec fn ordered<T>(s:Seq<T>,k:spec_fn(T)->int)->bool decreases s.len(){s.len()==0||(below(s[0],s,k)&&ordered(s.drop_first(),k))}
pub open spec fn count<T>(s:Seq<T>,x:T)->nat decreases s.len(){if s.len()==0{0}else{count(s.drop_first(),x)+if s[0]==x{1nat}else{0nat}}}
pub proof fn lemma_cons<T>(h:T,s:Seq<T>) ensures (seq![h]+s).len()==s.len()+1,(seq![h]+s).drop_first()==s,(seq![h]+s)[0]==h {assert((seq![h]+s).drop_first()=~=s);}
pub proof fn lemma_insert_length<T>(s:Seq<T>,x:T,k:spec_fn(T)->int) ensures insert(s,x,k).len()==s.len()+1,decreases s.len(){if s.len()>0&&k(x)>k(s[0]){lemma_insert_length(s.drop_first(),x,k);}}
pub proof fn lemma_insert_count<T>(s:Seq<T>,x:T,y:T,k:spec_fn(T)->int) ensures count(insert(s,x,k),y)==count(s,y)+if x==y{1nat}else{0nat},decreases s.len(){if s.len()>0{if k(x)<=k(s[0]){lemma_cons(x,s);}else{lemma_insert_count(s.drop_first(),x,y,k);lemma_cons(s[0],insert(s.drop_first(),x,k));}}}
pub proof fn lemma_below_cons<T>(h:T,x:T,s:Seq<T>,k:spec_fn(T)->int) requires k(h)<=k(x),below(h,s,k),ensures below(h,seq![x]+s,k),{assert forall|i:int|0<=i<(seq![x]+s).len() implies k(h)<=k(#[trigger] (seq![x]+s)[i]) by{if i>0{assert((seq![x]+s)[i]==s[i-1]);}}}
pub proof fn lemma_insert_below<T>(h:T,s:Seq<T>,x:T,k:spec_fn(T)->int)
 requires below(h,s,k),k(h)<=k(x),ensures below(h,insert(s,x,k),k),decreases s.len(),
 {if s.len()==0{lemma_below_cons(h,x,seq![],k);}else if k(x)<=k(s[0]){lemma_below_cons(h,x,s,k);}else{assert(below(h,s.drop_first(),k));lemma_insert_below(h,s.drop_first(),x,k);lemma_below_cons(h,s[0],insert(s.drop_first(),x,k),k);}}
pub proof fn lemma_insert_ordered<T>(s:Seq<T>,x:T,k:spec_fn(T)->int)
 requires ordered(s,k),ensures ordered(insert(s,x,k),k),decreases s.len(),
 {if s.len()==0{lemma_cons(x,seq![]);}else if k(x)<=k(s[0]){assert(below(x,s,k));lemma_below_cons(x,x,s,k);lemma_cons(x,s);}else{lemma_insert_ordered(s.drop_first(),x,k);assert(below(s[0],s.drop_first(),k));lemma_insert_below(s[0],s.drop_first(),x,k);lemma_below_cons(s[0],s[0],insert(s.drop_first(),x,k),k);lemma_cons(s[0],insert(s.drop_first(),x,k));}}
pub proof fn theorem_sort_ordered_and_length<T>(s:Seq<T>,k:spec_fn(T)->int)
 ensures ordered(sort(s,k),k),sort(s,k).len()==s.len(),decreases s.len(),
 {if s.len()>0{theorem_sort_ordered_and_length(s.drop_last(),k);lemma_insert_ordered(sort(s.drop_last(),k),s.last(),k);lemma_insert_length(sort(s.drop_last(),k),s.last(),k);}}
pub proof fn lemma_count_push<T>(s:Seq<T>,x:T,y:T) ensures count(s.push(x),y)==count(s,y)+if x==y{1nat}else{0nat},decreases s.len(){if s.len()>0{lemma_count_push(s.drop_first(),x,y);assert(s.push(x).drop_first()=~=s.drop_first().push(x));}}
pub proof fn theorem_sort_preserves_each_row<T>(s:Seq<T>,x:T,k:spec_fn(T)->int)
 ensures count(sort(s,k),x)==count(s,x),decreases s.len(),
 {if s.len()>0{theorem_sort_preserves_each_row(s.drop_last(),x,k);lemma_insert_count(sort(s.drop_last(),k),s.last(),x,k);lemma_count_push(s.drop_last(),s.last(),x);assert(s==s.drop_last().push(s.last()));}}
pub proof fn lemma_count_positive_iff_member<T>(s:Seq<T>,x:T) ensures count(s,x)>0<==>s.contains(x),decreases s.len(){if s.len()>0{lemma_count_positive_iff_member(s.drop_first(),x);assert(s==seq![s[0]]+s.drop_first());vstd::seq_lib::lemma_seq_concat_contains_all_elements(seq![s[0]],s.drop_first(),x);}}
}
